import socket 

from protocol_codec import encode_handshake, decode_handshake

def receive_exact(sock: socket.socket, size: int) -> bytes:

    '''
    Reads exactly the requested number of bytes from a socket.
    TCP may deliver data in smaller chunks
    '''

    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(size-len(data))

        if not chunk:
            raise ConnectionError("Connection closed during handshake")

        data.extend(chunk)

    return bytes(data)

def perform_handshake(sock: socket.socket, peer_id: int, expected_peer_id: int | None = None) -> int:
    '''
    Exchanges handshakes with another peer and verifies
    that we connected to the correct peer.
    '''
    #send 32-byte handshake
    sock.sendall(encode_handshake(peer_id))

    #read the other peer's complete handshake
    received = receive_exact(sock, 32)

    #decode the handshake to get the other peer's ID
    other_id = decode_handshake(received)

    #make sure the peer is who we expected
    if expected_peer_id is not None and other_id != expected_peer_id:
        raise ValueError(f"Expected Peer {expected_peer_id}, got peer {other_id}")

    return other_id
