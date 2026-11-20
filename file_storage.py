import os

def get_piece_size(piece_index: int, file_size: int, 
                   piece_size: int) -> int:
    '''Returns how many bytes piece_index should
      have (since the last piece can be shorter)'''
    offset = piece_index * piece_size
    remaining = file_size - offset
    if remaining <= 0:
        return 0
    if remaining < piece_size:
        return remaining
    return piece_size

def read_piece(peer_id: int, file_name: str, piece_index: int, 
               file_size: int, piece_size: int) -> bytes:
    # Reads piece's byte from this peer's file
    expected_len = get_piece_size(piece_index, file_size, piece_size)
    if expected_len <= 0:
        raise ValueError("Invalid piece index")
    
    filepath = os.path.join(f"peer_{peer_id}", file_name)
    offset = piece_index * piece_size
    file = open(filepath, "rb")

    try:
        file.seek(offset)
        data = file.read(expected_len)
    finally:
        file.close()

    if len(data) != expected_len:
        raise IOError("Could not read the full piece from the file")

    return data

def write_piece(peer_id: int, file_name: str, piece_index: int,
    data: bytes, file_size: int, piece_size: int) -> None:
    expected_len = get_piece_size(piece_index, file_size, piece_size)
   # Writes the downloaded piece to peer_[peerID]/file_name
    if expected_len <= 0:
        raise ValueError("Invalid piece index")
    
    if len(data) != expected_len:
        raise ValueError("Piece's size is not the expected piece size")

    dir = f"peer_{peer_id}"
    if not os.path.exists(dir):
        os.makedirs(dir)

    filepath = os.path.join(dir, file_name)
    offset = piece_index * piece_size
    
    if not os.path.exists(filepath):
        temp_file = open(filepath, "wb")
        temp_file.close()

    file = open(filepath, "r+b")
    try:
        file.seek(offset)
        file.write(data)
    finally:
        file.close()