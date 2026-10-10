from datetime import datetime

class EventLogger:
    def __init__(self, peer_id: int):
        '''
        initialize a logger for the given peer and
        creates its log file if needed
        '''
        self.peer_id = peer_id
        self.file_path = f"log_peer_{peer_id}.log"


        with open(self.file_path,"a"):
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


            


