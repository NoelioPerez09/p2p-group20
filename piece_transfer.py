import random
import socket
import struct
from file_storage import read_piece, write_piece
from peer_state import has_piece, num_owned_pieces, set_piece
from protocol_codec import encode_havereq_message, encode_piece_message

def pick_missing_piece(local_bitfield: bytearray, neigh_bitfield: bytearray, 
                       pending_requests: dict, num_pieces: int,) -> int | None:
    '''
    Selects a piece hat the neighbor has that we don't at random and returns its index
    '''
    if neigh_bitfield is None:
        return None

    candidates = []
    for i in range(num_pieces):
        if i in pending_requests or has_piece(local_bitfield, i):
            continue
        byte_index = i // 8
        mask = 1 << (7 - (i % 8))
        has_neigh = (neigh_bitfield[byte_index] & mask) != 0
        if has_neigh:
            candidates.append(i)

    if not candidates:
        return None

    return random.choice(candidates)

def send_piece_request(sock: socket.socket, neigh_id: int, piece_index: int,
    pending_requests: dict, message_type: dict) -> None:
    # Sends piece request to neigh_id 
    pending_requests[piece_index] = neigh_id
    request = encode_havereq_message(message_type["request"], piece_index)
    sock.sendall(request)

def handle_piece_request(sock: socket.socket, payload: bytes, peer_id: int, 
                         file_name: str, file_size: int, piece_size: int, local_bitfield: bytearray, 
                         is_unchoked_for_peer: bool) -> None:
    # Reads requested piece and sends it to the neighbor if it's unchoked
    if len(payload) < 4 or not is_unchoked_for_peer:
        return
    piece_index = struct.unpack(">I", payload[:4])[0]
    if not has_piece(local_bitfield, piece_index):
        return

    data = read_piece(peer_id, file_name, piece_index, file_size, piece_size)
    response = encode_piece_message(piece_index, data)
    sock.sendall(response)

def handle_piece_received(payload: bytes, peer_id: int, neigh_id: int, 
                          file_name: str, file_size: int, piece_size: int, local_bitfield: bytearray, 
                          pending_requests: dict) -> tuple[int, int] | None:
    '''
    Handles the processing for receiving a piece which includes
    saving the piece, updating local bitfield, and clearing pending request
    and then it returns the pieces' (index, count). 
    '''
    if len(payload) < 4:
        return None

    piece_index = struct.unpack(">I", payload[:4])[0]
    piece_data = payload[4:]

    if pending_requests.get(piece_index) == neigh_id:
        del pending_requests[piece_index]

    if has_piece(local_bitfield, piece_index):
        return None

    write_piece(peer_id, file_name, piece_index, piece_data, file_size, piece_size)
    set_piece(local_bitfield, piece_index)
    owned_count = num_owned_pieces(local_bitfield, (file_size + piece_size - 1) // piece_size)
    return piece_index, owned_count