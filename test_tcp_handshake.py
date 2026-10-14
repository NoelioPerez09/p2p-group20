
import socket
import threading
import unittest

from handshake import perform_handshake
from tcp.connection_manager import ConnectionManager


class TestTCPHandshake(unittest.TestCase):

    def test_tcp_handshake(self):
        '''
        Tests two peers connecting over TCP
        and successfully exchanging handshakes.
        '''
        #find two available local ports
        with socket.socket() as temp1, socket.socket() as temp2:
            temp1.bind(("127.0.0.1", 0))
            temp2.bind(("127.0.0.1", 0))
            port1 = temp1.getsockname()[1]
            port2 = temp2.getsockname()[1]

        peers = [
            {"peer_id": 1001, "host": "127.0.0.1", "port": port1},
            {"peer_id": 1002, "host": "127.0.0.1", "port": port2},
        ]

        manager1 = ConnectionManager(1001, peers)
        manager2 = ConnectionManager(1002, peers)

        results = {}
        errors = []

        def accept_peer():
            try:
                sock = manager1.accept_next()
                other_id = perform_handshake(sock, 1001)

                #verify the incoming peer is allowed
                if other_id != 1002:
                    raise ValueError("Unexpected incoming peer")

                results[1001] = other_id
            except Exception as error:
                errors.append(error)

        try:
            #both peers begin listening
            manager1.start_listening("127.0.0.1")
            manager2.start_listening("127.0.0.1")

            #peer 1001 waits for an incoming connection.
            thread = threading.Thread(target=accept_peer)
            thread.start()

            #peer 1002 connects to Peer 1001
            connections = manager2.connect_to_previous()
            sock = connections[1001]

            results[1002] = perform_handshake(sock, 1002, 1001)

            thread.join(timeout=5)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(results[1001], 1002)
            self.assertEqual(results[1002], 1001)

        finally:
            manager1.close()
            manager2.close()
