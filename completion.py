import socket
import threading
from event_logger import EventLogger
from peer_state import num_owned_pieces
from tcp import ConnectionManager

def is_bitfield_complete(bitfield: bytearray, num_pieces: int) -> bool:
    '''
    Returns True if all of the pieces are set in the given bitfield
    and false if the contrary is the case
    '''
    
    if bitfield is None or num_pieces <= 0:
        return False
    return num_owned_pieces(bitfield, num_pieces) == num_pieces

def local_completion(state: dict, logger: EventLogger) -> None:
    # Determines if the peer should log_download_complete or not and if it should it logs it
    should_log = False
    with state["lock"]:
        if not state["logged_complete"] and is_bitfield_complete(state["local_bitfield"], state["num_pieces"]):
            state["logged_complete"] = True
            should_log = True

    if should_log:
        logger.log_download_complete()

def all_complete_file(state: dict, all_peer_ids: list[int]) -> bool:
    # Returns True when all configured peers have the full file and false if the contrary is the case
    with state["lock"]:
        num_pieces = state["num_pieces"]
        if not is_bitfield_complete(state["local_bitfield"], num_pieces):
            return False

        for peer_id in all_peer_ids:
            if peer_id == state["peer_id"]:
                continue
            neigh_bf = state["neigh_bitfields"].get(peer_id)
            if not is_bitfield_complete(neigh_bf, num_pieces):
                return False

    return True

def shutdown_peer(state: dict, send_locks: dict[int, threading.Lock], connected: dict[int, socket.socket], 
                  manager: ConnectionManager, threads: list[threading.Thread]) -> None:

    with state["lock"]:
        state["stop"] = True

    for neigh_id, sock in list(connected.items()):
        lock = send_locks.get(neigh_id)
        try:
            if lock is not None:
                with lock:
                    sock.shutdown(socket.SHUT_RDWR)
            else:
                sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    for thread in threads:
        if thread.is_alive():
            thread.join(timeout=3)

    manager.close()