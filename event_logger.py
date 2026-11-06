from datetime import datetime

class EventLogger:
    def __init__(self, peer_id: int):
        '''
        initialize a logger for the given peer and
        creates its log file if needed
        '''
        self.peer_id = peer_id
        self.file_path = f"log_peer_{peer_id}.log"

        with open(self.file_path, "a"):
            pass

    def log_event(self, event: str):
        '''
        log an event to the peer's log file
        '''
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #append so earlier events aren't lost
        with open(self.file_path, "a") as file:
            file.write(f"[{timestamp}]: {event}\n")

    def log_connection_made(self, other_id: int):
        '''
        Records when this peer connects to another peer
        '''
        message = f"Peer {self.peer_id} makes a connection to Peer {other_id}."
        self.log_event(message)

    def log_connection_received(self, other_id: int):
        '''
        Records when this peer receives a connection from another peer
        '''
        message = f"Peer {self.peer_id} is connected from Peer {other_id}."
        self.log_event(message)

    def log_preferred_neighbors(self, neighbor_ids: list[int]):
        '''
        log the preferred neighbors whenever they change
        '''
        neighbors = ", ".join(str(peer_id) for peer_id in neighbor_ids)
        message = f"Peer {self.peer_id} has the preferred neighbors {neighbors}."
        self.log_event(message)

    def log_optimistic_unchoke(self, neighbor_id: int):
        '''
        log when a new optimistic neighbor is selected
        '''
        message = f"Peer {self.peer_id} has the optimistically unchoked neighbor {neighbor_id}."
        self.log_event(message)

    def log_unchoked(self, other_id: int):
        '''
        log when this peer gets unchoked by another peer
        '''
        message = f"Peer {self.peer_id} is unchoked by {other_id}."
        self.log_event(message)

    def log_choked(self, other_id: int):
        '''
        log when this peer gets choked by another peer
        '''
        message = f"Peer {self.peer_id} is choked by {other_id}."
        self.log_event(message)

    def log_have(self, other_id: int, piece_index: int):
        '''
        log when a have message is received from another peer
        '''
        message = f"Peer {self.peer_id} received the 'have' message from {other_id} for the piece {piece_index}."
        self.log_event(message)

    def log_interested(self, other_id: int):
        '''
        log when another peer sends an interested message
        '''
        message = f"Peer {self.peer_id} received the 'interested' message from {other_id}."
        self.log_event(message)

    def log_not_interested(self, other_id: int):
        '''
        log when another peer sends a not interested message
        '''
        message = f"Peer {self.peer_id} received the 'not interested' message from {other_id}."
        self.log_event(message)

    def log_piece_downloaded(self, other_id: int, piece_index: int, num_pieces: int):
        '''
        log when a piece finishes downloading and update the piece count
        '''
        message = (
            f"Peer {self.peer_id} has downloaded the piece {piece_index} "
            f"from {other_id}. Now the number of pieces it has is {num_pieces}."
        )
        self.log_event(message)

    def log_download_complete(self):
        '''
        log when this peer has downloaded the full file
        '''
        message = f"Peer {self.peer_id} has downloaded the complete file."
        self.log_event(message)
