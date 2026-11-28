import socket
import threading
import queue

def send_to_peer(send_locks: dict[int, threading.Lock],
                 connected: dict[int, socket.socket],
                 neigh_id: int, message: bytes) -> bool:
    '''
    sends a message safely without allowing multiple
    threads to write to the same socket simultaneously
    '''
    connection = connected.get(neigh_id)
    lock = send_locks.get(neigh_id)

    if connection is None or lock is None:
        return False

    try:
        with lock:
            connection.sendall(message)
        return True

    except OSError:
        return False

def send_messages(connection: socket.socket,
                  outgoing: queue.Queue,
                  stop_event: threading.Event) -> None:
    # Sends queued messages in order until the connection is stopped
    try:
        while not stop_event.is_set():
            try:
                message = outgoing.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                connection.sendall(message)
            finally:
                outgoing.task_done()

    except OSError:
        # Closes the connection if sending fails
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class QueuedConnection:
    '''
    Wraps a socket so outgoing messages are queued
    while incoming messages are received normally.
    '''
    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.outgoing = queue.Queue()

    def sendall(self, message: bytes) -> None:
        #add the message to the outgoing queue
        self.outgoing.put(message)

    def recv(self, size: int) -> bytes:
        return self.connection.recv(size)

    def shutdown(self, how: int) -> None:
        self.connection.shutdown(how)

    def close(self) -> None:
        self.connection.close()