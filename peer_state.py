def create_initial_bitfield(num_pieces: int, has_file: bool) -> bytearray:
    # Creates the initial bitfield bytearray for a peer.
    num_bytes = (num_pieces + 7) // 8
    bitfield = bytearray(num_bytes)
    
    if has_file:
        for i in range(num_bytes):
            bitfield[i] = 0xFF
        remainder = num_pieces % 8
        if remainder != 0:
            valid_bits_mask = 0xFF << (8 - remainder) & 0xFF
            bitfield[-1] = valid_bits_mask
            
    return bitfield

def has_piece(bitfield: bytearray, index: int) -> bool:
    '''
    Returns True if the specific piece is set in the bitfield
    bytearray and False if the contrary is the case
    '''
    byte_index = index // 8
    bit_offset = index % 8
    target_bit_mask = 1 << (7 - bit_offset)

    if byte_index >= len(bitfield):
        return False
        
    return (bitfield[byte_index] & target_bit_mask) != 0

def set_piece(bitfield: bytearray, index: int) -> None:
    '''
     Sets the bit of the specific piece to 1 (owned)
     in the given bitfield bytearray. 
    '''
    byte_index = index // 8
    bit_offset = index % 8
    target_bit_mask = 1 << (7 - bit_offset)

    if byte_index < len(bitfield):
        bitfield[byte_index] |= target_bit_mask

def num_owned_pieces(bitfield: bytearray, num_pieces: int) -> int:
    '''
    Calculates and returns the number of pieces currently owned
    according to the input bitfield bytearray
    '''
    count = 0
    for i in range(num_pieces):
        if has_piece(bitfield, i):
            count += 1
    return count

def store_neigh_bitfield(neigh_bitfields: dict, neigh_id: int, 
                         bitfield_bytes: bytes, num_pieces: int) -> None:
    # Saves or updates the input bitfield (from a neighbor) in a dict
    num_bytes = (num_pieces + 7) // 8
    bytes = bytearray(bitfield_bytes.ljust(num_bytes, b'\x00')[:num_bytes])
    neigh_bitfields[neigh_id] = bytes

def is_interested_in(bitfield: bytearray, 
                     neigh_bitfield: bytearray, num_pieces: int) -> bool:
    '''
    Returns True if this peer should be interested in a neighbor's data 
    and False if the contrary is the case
    '''
    if neigh_bitfield is None:
        return False
        
    for i in range(num_pieces):
        byte_index = i // 8
        bit_offset = i % 8
        mask = 1 << (7 - bit_offset)
        
        remote = (neigh_bitfield[byte_index] & mask) != 0
        local = (bitfield[byte_index] & mask) != 0
        
        if remote and not local:
            return True
            
    return False