"""Blocking IP TCP connection setup."""

import socket


def recv_exact(connection: socket.socket, size: int) -> bytes:
    '''Reads size bytes'''
    if size < 0:
        raise ValueError("size must not be negative")
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise EOFError("Peer disconnected before all bytes arrived")
        data.extend(chunk)
    return bytes(data)


class ConnectionManager:
    def __init__(self, peer_id: int, all_peers: list[dict], timeout: float = 5):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.peer_id = peer_id
        self.timeout = timeout
        self.peers = []
        ids = set()
        for peer in all_peers:
            record = dict(peer)
            other_id = record["peer_id"]
            if other_id in ids:
                raise ValueError("Duplicate peer ID")
            ids.add(other_id)
            record["port"] = int(record["port"])
            if not 1 <= record["port"] <= 65535 or not record["host"]:
                raise ValueError("Invalid host or port")
            self.peers.append(record)
        if peer_id not in ids:
            raise ValueError("This peer is missing from PeerInfo.cfg")
        index = next(i for i, p in enumerate(self.peers) if p["peer_id"] == peer_id)
        self.self_info = self.peers[index]
        self.previous_peers = self.peers[:index]
        self.later_peers = self.peers[index + 1:]
        self.listener = None
        self.outgoing = {}
        self.accepted = []

    def start_listening(self, bind_host: str = "0.0.0.0"):
        '''Connection Listener starter'''
        if self.listener is not None:
            return
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            #Restarts a peer fast
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((bind_host, self.self_info["port"]))
            listener.listen(max(1, len(self.later_peers)))
            listener.settimeout(self.timeout)
        except BaseException:
            listener.close()
            raise
        self.listener = listener

    def connect_to_previous(self) -> dict[int, socket.socket]:
        '''Connects once to each earlier peer'''
        if self.listener is None:
            raise RuntimeError("Call start_listening before connecting")
        try:
            for peer in self.previous_peers:
                other_id = peer["peer_id"]
                if other_id in self.outgoing:
                    continue
                connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    connection.settimeout(self.timeout)
                    connection.connect((peer["host"], peer["port"]))
                    connection.settimeout(None)
                except BaseException:
                    connection.close()
                    raise
                self.outgoing[other_id] = connection
        except BaseException:
            self.close()
            raise
        return dict(self.outgoing)

    def accept_next(self) -> socket.socket:
        '''Return a raw connection; its address and arrival order are not IDs.'''
        if self.listener is None:
            raise RuntimeError("Call start_listening before accepting")
        connection, _ = self.listener.accept()
        try:
            connection.settimeout(None)
        except BaseException:
            connection.close()
            raise
        self.accepted.append(connection)
        return connection

    def close(self):
        '''Release every owned socket, including unidentified accepted peers.'''
        connections = list(self.outgoing.values()) + self.accepted
        if self.listener is not None:
            connections.append(self.listener)
        self.listener = None
        self.outgoing.clear()
        self.accepted.clear()
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                # Still release the remaining sockets if one close fails.
                pass
