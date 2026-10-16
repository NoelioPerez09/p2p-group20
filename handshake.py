import socket

from protocol_codec import encode_handshake, decode_handshake
from tcp import recv_exact

def perform_handshake(sock: socket.socket, peer_id: int, expected_peer_id: int | None = None) -> int:
    '''
    Exchanges handshakes with another peer and verifies
    it is indeed the correct peer the one for which it is connected to.
    '''
    #handshake sending
    sock.sendall(encode_handshake(peer_id))

    #handshake reading
    received = recv_exact(sock, 32)
    other_id = decode_handshake(received)

    #check that peer_id is the one who is the expected one
    if expected_peer_id is not None and other_id != expected_peer_id:
        raise ValueError(f"Expected Peer {expected_peer_id}, got peer {other_id}")

    return other_id

def perform_incoming_handshake(sock: socket.socket, peer_id: int, allowed_peer_ids: set[int]) -> int:
    '''
    Handshake exchange with connected peer. 
    Reads and then checks if ID is on the allowed_peer_ids set. 
    Returns the other's peer's id
    '''
    #sends handshake first
    sock.sendall(encode_handshake(peer_id))

    #handshake decoder
    other_id = decode_handshake(recv_exact(sock, 32))
    if other_id not in allowed_peer_ids:
        raise ValueError(f"Peer {other_id} is not an allowed incoming peer")

    return other_id
