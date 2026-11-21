import socket
import struct
from protocol_codec import decode_message, encode_bitfield_message, encode_message
from tcp import recv_exact

def recv_framed_message(sock: socket.socket) -> tuple[int, bytes]:
    # Reads one message from stream and returns (msg_type, payload)
    length_bytes = recv_exact(sock, 4)
    msg_length = struct.unpack(">I", length_bytes)[0]

    if msg_length < 1:
        raise ValueError("Invalid message length")
    
    body = recv_exact(sock, msg_length)
    return decode_message(body)

def exchange_bitfield_interest(sock: socket.socket, peer_id: int,
    neigh_id: int, local_bitfield: bytearray, neigh_bitfields: dict,
    num_pieces: int, has_any_piece: bool, message_type: dict) -> bool: 
    '''Exchanges initial bitfields after the 
    handshake to the peer and sends interested 
    or not interested to the peer.'''
    if has_any_piece:
        bitfield_msg = encode_bitfield_message(bytes(local_bitfield))
        sock.sendall(bitfield_msg)

    msg_type, payload = recv_framed_message(sock)
    if msg_type == message_type["bitfield"]:
        neigh_bitfields[neigh_id] = bytearray(payload.ljust((num_pieces + 7) // 8, 
                                                            b"\x00")[: (num_pieces + 7) // 8])
        interest_type, interest_payload = recv_framed_message(sock)
    else:
        neigh_bitfields[neigh_id] = bytearray((num_pieces + 7) // 8)
        interest_type = msg_type
    peer_interested_us = interest_type == message_type["interested"]
    we_want_pieces = False
    neigh_bitfield = neigh_bitfields[neigh_id]

    for i in range(num_pieces):
        byte_index = i // 8
        mask = 1 << (7 - (i % 8))
        neigh_has = (neigh_bitfield[byte_index] & mask) != 0
        us_have = (local_bitfield[byte_index] & mask) != 0
        
        if neigh_has and not us_have:
            we_want_pieces = True
            break

    if we_want_pieces:
        reply = encode_message(message_type["interested"])
    else:
        reply = encode_message(message_type["not_interested"])

    sock.sendall(reply)
    return peer_interested_us