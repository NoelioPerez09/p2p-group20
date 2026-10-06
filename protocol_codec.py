import struct

# Constants
HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"
ZERO_BITS = b"\x00" * 10         

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
    try:
        decoded_handshake = struct.unpack(">18s10sI", encoded_handshake)
    except:
        raise(ValueError) 
    length_sum = len(decoded_handshake[0]) + len(decoded_handshake[1]) + len(str(decoded_handshake[2]))
    if length_sum != 32:
        raise(ValueError)
    if decoded_handshake[0] != HANDSHAKE_HEADER:
        raise(ValueError)
    return decoded_handshake[2]
