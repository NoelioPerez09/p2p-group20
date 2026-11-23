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
    '''
    exchanges bitfields after handshake and checks if
    either peer is interested in the other's pieces
    '''
    #always send bitfield, even if we dont have any pieces yet
    bitfield_msg = encode_bitfield_message(bytes(local_bitfield))
    sock.sendall(bitfield_msg)

    #read the neighbor's first message
    msg_type, payload = recv_framed_message(sock)

    if msg_type == message_type["bitfield"]:
        num_bytes = (num_pieces + 7) // 8
        neigh_bitfields[neigh_id] = bytearray(
            payload.ljust(num_bytes, b"\x00")[:num_bytes]
        )
    else:
        #neighbor didnt send a bitfield
        neigh_bitfields[neigh_id] = bytearray((num_pieces + 7) // 8)

    #check if they have any pieces we need
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

    #send our interest before waiting for theirs
    if we_want_pieces:
        reply = encode_message(message_type["interested"])
    else:
        reply = encode_message(message_type["not_interested"])

    sock.sendall(reply)

    #get their interest message
    if msg_type == message_type["bitfield"]:
        interest_type, _ = recv_framed_message(sock)
    else:
        interest_type = msg_type

    peer_interested_us = interest_type == message_type["interested"]
    return peer_interested_us
