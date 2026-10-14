import socket

from protocol_codec import encode_handshake, decode_handshake
from tcp import recv_exact

def perform_handshake(sock: socket.socket, peer_id: int, expected_peer_id: int | None = None) -> int:
    '''
    Exchanges handshakes with another peer and verifies
    that we connected to the correct peer.
    Used when WE dialed out, so we know who to expect.
    '''
    #send 32-byte handshake
    sock.sendall(encode_handshake(peer_id))

    #read the other peer's complete handshake
    received = recv_exact(sock, 32)

    #decode the handshake to get the other peer's ID
    other_id = decode_handshake(received)

    #make sure the peer is who we expected
    if expected_peer_id is not None and other_id != expected_peer_id:
        raise ValueError(f"Expected Peer {expected_peer_id}, got peer {other_id}")

    return other_id

def perform_incoming_handshake(sock: socket.socket, peer_id: int, allowed_peer_ids: set[int]) -> int:
    '''
    Exchanges handshakes with a peer that connected to us.
    We can't know who is calling until their handshake arrives,
    so we read it first and then check it is one of the allowed IDs.
    Returns the caller's peer ID
    '''
    #send our handshake first, both sides send before reading so nobody waits
    sock.sendall(encode_handshake(peer_id))

    #read the caller's handshake to learn who they are
    other_id = decode_handshake(recv_exact(sock, 32))

    #reject callers that aren't in the allowed set
    if other_id not in allowed_peer_ids:
        raise ValueError(f"Peer {other_id} is not an allowed incoming peer")

    return other_id
