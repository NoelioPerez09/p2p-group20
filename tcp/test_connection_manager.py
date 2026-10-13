"""TCP tests; use loopback only and leave team configuration alone."""

import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch

from tcp import ConnectionManager, recv_exact


def peers():
    # Deliberately different from numeric order; config ports are strings.
    return [{"peer_id": i, "host": "127.0.0.1", "port": str(p)}
            for i, p in [(1003, 6101), (1001, 6102), (1002, 6103)]]


class ConnectionManagerTests(unittest.TestCase):
    def test_config_order_and_no_input_changes(self):
        records = peers()
        manager = ConnectionManager(1001, records)
        self.assertEqual([p["peer_id"] for p in manager.previous_peers], [1003])
        self.assertEqual([p["peer_id"] for p in manager.later_peers], [1002])
        self.assertEqual(manager.self_info["port"], 6102)
        self.assertEqual(records[1]["port"], "6102")

    def test_missing_self(self):
        with self.assertRaises(ValueError):
            ConnectionManager(9999, peers())

    def test_duplicate_id(self):
        with self.assertRaises(ValueError):
            ConnectionManager(1001, peers() + [peers()[1]])

    def test_invalid_port(self):
        for port in ["bad", "0", "65536"]:
            with self.subTest(port=port), self.assertRaises(ValueError):
                ConnectionManager(1001, [{**peers()[1], "port": port}])

    def test_invalid_timeout(self):
        for timeout in [0, -1]:
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                ConnectionManager(1001, peers(), timeout)

    def test_operations_require_listener(self):
        manager = ConnectionManager(1001, peers())
        for operation in [manager.accept_next, manager.connect_to_previous]:
            with self.assertRaises(RuntimeError):
                operation()

    @patch("tcp.connection_manager.socket.socket")
    def test_listener_bind_and_idempotence(self, factory):
        manager = ConnectionManager(1001, peers())
        manager.start_listening("127.0.0.1")
        manager.start_listening()
        factory.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        factory.return_value.bind.assert_called_once_with(("127.0.0.1", 6102))
        factory.return_value.listen.assert_called_once_with(1)
        manager.close()

    @patch("tcp.connection_manager.socket.socket")
    def test_bind_failure_closes_listener(self, factory):
        factory.return_value.bind.side_effect = OSError("address in use")
        manager = ConnectionManager(1001, peers())
        with self.assertRaises(OSError):
            manager.start_listening()
        factory.return_value.close.assert_called_once()
        self.assertIsNone(manager.listener)

    @patch("tcp.connection_manager.socket.socket")
    def test_connect_order_no_duplicates_and_blocking_result(self, factory):
        listener, first, second = Mock(), Mock(), Mock()
        factory.side_effect = [listener, first, second]
        manager = ConnectionManager(1002, peers())
        manager.start_listening()
        result = manager.connect_to_previous()
        self.assertEqual(list(result), [1003, 1001])
        first.connect.assert_called_once_with(("127.0.0.1", 6101))
        second.connect.assert_called_once_with(("127.0.0.1", 6102))
        self.assertEqual(first.settimeout.call_args_list[-1].args, (None,))
        self.assertEqual(manager.connect_to_previous(), result)
        result.clear()
        self.assertEqual(len(manager.outgoing), 2)
        manager.close()

    @patch("tcp.connection_manager.socket.socket")
    def test_connect_failure_rolls_back_all_sockets(self, factory):
        listener, first, second = Mock(), Mock(), Mock()
        factory.side_effect = [listener, first, second]
        second.connect.side_effect = ConnectionRefusedError()
        manager = ConnectionManager(1002, peers())
        manager.start_listening()
        accepted = Mock()
        listener.accept.return_value = (accepted, ("127.0.0.1", 45678))
        manager.accept_next()
        with self.assertRaises(ConnectionRefusedError):
            manager.connect_to_previous()
        for connection in [listener, first, second, accepted]:
            connection.close.assert_called_once()
        self.assertEqual(manager.outgoing, {})
        self.assertEqual(manager.accepted, [])
        self.assertIsNone(manager.listener)

    def test_accept_returns_unidentified_socket(self):
        manager = ConnectionManager(1001, peers())
        manager.listener = Mock()
        incoming = Mock()
        manager.listener.accept.return_value = (incoming, ("127.0.0.1", 50000))
        self.assertIs(manager.accept_next(), incoming)
        self.assertEqual(manager.outgoing, {})
        self.assertEqual(manager.accepted, [incoming])
        incoming.settimeout.assert_called_once_with(None)
        manager.close()

    def test_accept_timeout_keeps_listener(self):
        manager = ConnectionManager(1001, peers())
        listener = Mock()
        manager.listener = listener
        listener.accept.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            manager.accept_next()
        self.assertIs(manager.listener, listener)
        manager.close()

    def test_accepted_socket_setup_failure_closes_socket(self):
        manager = ConnectionManager(1001, peers())
        manager.listener = Mock()
        incoming = Mock()
        incoming.settimeout.side_effect = OSError("socket setup failed")
        manager.listener.accept.return_value = (incoming, ("127.0.0.1", 50000))
        with self.assertRaises(OSError):
            manager.accept_next()
        incoming.close.assert_called_once()
        self.assertEqual(manager.accepted, [])
        manager.close()

    def test_close_is_idempotent_after_disconnect(self):
        manager = ConnectionManager(1001, peers())
        connection = Mock()
        connection.shutdown.side_effect = OSError("already disconnected")
        manager.accepted.append(connection)
        manager.close()
        manager.close()
        connection.close.assert_called_once()

    def test_close_error_does_not_skip_remaining_sockets(self):
        manager = ConnectionManager(1001, peers())
        first, second, listener = Mock(), Mock(), Mock()
        first.close.side_effect = OSError("socket close failed")
        manager.outgoing[1003] = first
        manager.accepted.append(second)
        manager.listener = listener
        manager.close()
        manager.close()
        for connection in [first, second, listener]:
            connection.close.assert_called_once()
        self.assertEqual(manager.outgoing, {})
        self.assertEqual(manager.accepted, [])
        self.assertIsNone(manager.listener)

    def test_real_ipv4_connection_and_cleanup(self):
        manager = ConnectionManager(1001, peers(), timeout=1)
        # Port zero is test-only to ask the OS for an available loopback port.
        manager.self_info["port"] = 0
        manager.start_listening("127.0.0.1")
        listener = manager.listener
        client = socket.create_connection(listener.getsockname(), timeout=1)
        try:
            incoming = manager.accept_next()
            client.sendall(b"ping")
            self.assertEqual(recv_exact(incoming, 4), b"ping")
            incoming.sendall(b"pong")
            self.assertEqual(recv_exact(client, 4), b"pong")
            manager.close()
            self.assertEqual(client.recv(1), b"")
            self.assertEqual(incoming.fileno(), -1)
            self.assertEqual(listener.fileno(), -1)
        finally:
            client.close()
            manager.close()

    def test_missing_earlier_peer_is_bounded_and_cleans_up(self):
        # First earlier peer listens; second reserves a port but never listens.
        # No DNS or port-selection race is involved in this loopback failure.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as earlier, \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM) as missing:
            earlier.bind(("127.0.0.1", 0))
            earlier.listen(1)
            earlier.settimeout(2)
            missing.bind(("127.0.0.1", 0))
            records = peers()
            records[0]["port"] = str(earlier.getsockname()[1])
            records[1]["port"] = str(missing.getsockname()[1])
            manager = ConnectionManager(1002, records, timeout=0.25)
            manager.self_info["port"] = 0
            manager.start_listening("127.0.0.1")
            listener = manager.listener
            client = socket.create_connection(listener.getsockname(), timeout=2)
            try:
                incoming = manager.accept_next()
                began = time.monotonic()
                with self.assertRaises(OSError):
                    manager.connect_to_previous()
                elapsed = time.monotonic() - began
                self.assertLess(elapsed, 3, "Connect failure exceeded test deadline")
                self.assertIsNone(manager.listener)
                self.assertEqual(manager.outgoing, {})
                self.assertEqual(manager.accepted, [])
                self.assertEqual(listener.fileno(), -1)
                self.assertEqual(incoming.fileno(), -1)
                self.assertEqual(client.recv(1), b"")
                connected, _ = earlier.accept()
                with connected:
                    connected.settimeout(2)
                    self.assertEqual(connected.recv(1), b"")
                manager.close()
                print(f"PASS: missing earlier peer failed in {elapsed:.3f}s "
                      "(0.25s socket timeout, 3s test deadline); "
                      "listener, prior outgoing and accepted sockets closed")
            finally:
                client.close()
                manager.close()


class ExactReadTests(unittest.TestCase):
    def test_fragmented_read_and_no_overread(self):
        connection = Mock()
        connection.recv.side_effect = [b"a", b"bc", b"d"]
        self.assertEqual(recv_exact(connection, 4), b"abcd")
        self.assertEqual([c.args[0] for c in connection.recv.call_args_list], [4, 3, 1])

    def test_empty_read(self):
        connection = Mock()
        self.assertEqual(recv_exact(connection, 0), b"")
        connection.recv.assert_not_called()

    def test_negative_read(self):
        with self.assertRaises(ValueError):
            recv_exact(Mock(), -1)

    def test_eof_before_or_during_read(self):
        for chunks in [[b""], [b"ab", b""]]:
            with self.subTest(chunks=chunks), self.assertRaises(EOFError):
                recv_exact(Mock(recv=Mock(side_effect=chunks)), 4)

    def test_timeout_and_reset_propagate(self):
        for error in [TimeoutError, ConnectionResetError]:
            with self.subTest(error=error), self.assertRaises(error):
                recv_exact(Mock(recv=Mock(side_effect=error())), 4)

    def test_real_partial_io_and_early_disconnect(self):
        left, right = socket.socketpair()
        left.settimeout(2)
        right.settimeout(2)
        def send_fragments():
            try:
                for chunk in [b"a", b"bc", b"def"]:
                    right.sendall(chunk)
                right.shutdown(socket.SHUT_WR)
            finally:
                right.close()
        sender = threading.Thread(target=send_fragments)
        sender.start()
        try:
            self.assertEqual(recv_exact(left, 5), b"abcde")
            with self.assertRaises(EOFError):
                recv_exact(left, 2)
        finally:
            left.close()
            sender.join(3)
        self.assertFalse(sender.is_alive())


if __name__ == "__main__":
    unittest.main()
