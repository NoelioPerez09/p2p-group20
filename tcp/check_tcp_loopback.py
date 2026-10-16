"""Loopback checks for peer TCP connections that allows for multiple processess.
Run: python3 check_tcp_loopback.py
"""

import multiprocessing
from pathlib import Path
import queue
import socket
import tempfile
import os
import traceback
import time

from tcp import ConnectionManager, recv_exact
from event_logger import EventLogger
from handshake import perform_handshake
from protocol_codec import encode_handshake, decode_handshake


def worker(peer_id, records, barrier, results, log_directory, started=None):
    manager = ConnectionManager(peer_id, records, timeout=10)
    try:
        os.chdir(log_directory)
        logger = EventLogger(peer_id)
        manager.start_listening("127.0.0.1")
        if started is None:
            barrier.wait(timeout=15)
        else:
            # Continue directly into real connect/accept work while later peers do not exist yet. 
            started.put(peer_id)
        outgoing = manager.connect_to_previous()
        identified = dict(outgoing)
        for expected, connection in outgoing.items():
            connection.settimeout(10)
            perform_handshake(connection, peer_id, expected)
            logger.log_connection_made(expected)
        allowed = {p["peer_id"] for p in manager.later_peers}
        for _ in allowed:
            connection = manager.accept_next()
            connection.settimeout(10)
            # As of this point, identity of incoming peer is currently uknown. 
            handshake = encode_handshake(peer_id)
            connection.sendall(handshake[:7])
            connection.sendall(handshake[7:])
            other = decode_handshake(recv_exact(connection, 32))
            if other not in allowed or other in identified:
                raise AssertionError("Unexpected or duplicate incoming peer ID")
            identified[other] = connection
            logger.log_connection_received(other)
        if len(identified) != len(records) - 1:
            raise AssertionError("Incomplete mesh")
        # Test-only payload after all handshakes.
        barrier.wait(timeout=15)
        payload = bytes([peer_id % 256]) * 8192
        for connection in identified.values():
            connection.sendall(payload)
        for other, connection in identified.items():
            if recv_exact(connection, len(payload)) != bytes([other % 256]) * len(payload):
                raise AssertionError("Payload mismatch")
        barrier.wait(timeout=15)
        for connection in identified.values():
            connection.shutdown(socket.SHUT_WR)
        for connection in identified.values():
            if connection.recv(1) != b"":
                raise AssertionError("Expected clean EOF")
        manager.close()
        lines = Path(logger.file_path).read_text().splitlines()
        if len(lines) != len(records) - 1:
            raise AssertionError("Missing connection log entries")
        results.put((peer_id, len(identified), "PASS"))
    except BaseException:
        results.put((peer_id, 0, traceback.format_exc()))
        barrier.abort()
    finally:
        manager.close()


def check(count, staggered=False):
    # Reserve distinct ports and selects them. Then it releases for child processes. 
    reservations = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(count)]
    try:
        for reservation in reservations:
            reservation.bind(("127.0.0.1", 0))
        ids = [1003, 1001, 1006, 1002, 1005, 1004][:count]
        records = [{"peer_id": i, "host": "127.0.0.1", "port": str(s.getsockname()[1])}
                   for i, s in zip(ids, reservations)]
    finally:
        for reservation in reservations:
            reservation.close()
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(count)
    results = context.Queue()
    started = context.Queue() if staggered else None
    with tempfile.TemporaryDirectory() as directory:
        processes = [context.Process(target=worker, args=(i, records, barrier, results, directory, started))
                     for i in ids]
        try:
            for peer_id, process in zip(ids, processes):
                process.start()
                if started is not None:
                    if started.get(timeout=10) != peer_id:
                        raise AssertionError("Peers did not start in file order")
                    time.sleep(0.15)
            outcomes = []
            for i in processes:
                try:
                    outcomes.append(results.get(timeout=30))
                except queue.Empty:
                    raise AssertionError("Timed out waiting for a peer")
            for process in processes:
                process.join(timeout=5)
            if any(p.is_alive() or p.exitcode != 0 for p in processes):
                raise AssertionError("A peer did not exit successfully")
            if any(status != "PASS" for _, _, status in outcomes):
                raise AssertionError(outcomes)
            assert all(neighbors == count - 1 for _, neighbors, _ in outcomes)
            mode = "staggered file-order startup" if staggered else "all listeners ready"
            print(f"PASS: {count} processes ({mode}), "
                  f"{count * (count - 1) // 2} full-duplex pairs; "
                  "handshakes, payloads, logs, and cleanup")
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                if process.pid is not None:
                    process.join(timeout=5)
            results.close()
            results.join_thread()
            if started is not None:
                started.close()
                started.join_thread()


if __name__ == "__main__":
    for count in (2, 3, 6):
        check(count)
        check(count, staggered=True)
