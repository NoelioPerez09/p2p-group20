import struct

# Constants
HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"
ZERO_BITS = b"\x00" * 10
message_type = {
    "choke": 0,
    "unchoke": 1,
    "interested": 2,
    "not_interested": 3,
    "have": 4,
    "bitfield": 5,
    "request": 6,
    "piece": 7
}         

def encode_handshake(peer_id : int) -> bytes:
    '''
    Returns the encoded 32-Byte Handshake as 
    'P2PFILESHARINGPROJ' (18 bytes) + 
    '0000000000' (10 bytes) + 
    peer_id (4 bytes)
    '''
    return struct.pack(">18s10sI", HANDSHAKE_HEADER, ZERO_BITS, peer_id)

def decode_handshake(encoded_handshake : bytes) -> int:
    '''
    Decodes a given encoded handshake, 
    raises ValueError if 
    len(encoded_handshake) != 32 or
    first 18 bytes are not 
    'P2PFILESHARINGPROJ'. Returns
    peer_id from encoded handshake
    '''
    if len(encoded_handshake) != 32:
        raise ValueError("Handshake must be exactly 32 bytes")
    try:
        decoded_handshake = struct.unpack(">18s10sI", encoded_handshake)
    except:
        raise(ValueError) 
    if decoded_handshake[0] != HANDSHAKE_HEADER:
        raise(ValueError)
    return decoded_handshake[2]

def encode_message(msg_type: int, payload: bytes = b"") -> bytes:
    # Encodes a message into bytes for transmission
    if not (0 <= msg_type <= 7):
        raise ValueError(f"Invalid message type: {msg_type}")
    
    length = 1 + len(payload)
    header = struct.pack(">IB", length, msg_type)
    return header + payload

def decode_message(body: bytes) -> tuple[int, bytes]:
    # Decodes the body of a message (after reading the length)
    if len(body) == 0:
        raise ValueError("Empty body")
    
    msg_type = body[0]
    payload = body[1:]
    
    if not (0 <= msg_type <= 7):
        raise ValueError(f"Invalid message type: {msg_type}")
        
    return msg_type, payload

def encode_havereq_message(msg_type: int, piece_index: int) -> bytes:
    # Encodes either have messages (type 4) or request messages (type 6)
    payload = struct.pack(">I", piece_index)
    return encode_message(msg_type, payload)

def encode_bitfield_message(bitfield_bytes: bytes) -> bytes:
    # Encodes bitfield messages (type 5)
    return encode_message(message_type['bitfield'], bitfield_bytes)

def encode_piece_message(piece_index: int, piece_data: bytes) -> bytes:
    # Encodes piece messages (type 7)
    payload = struct.pack(">I", piece_index) + piece_data
    return encode_message(message_type['piece'], payload)