import socket
import threading
import time
from choking import chocke_changes, select_optimistic_neighbor, select_preferred_neighbors
from event_logger import EventLogger
from peer_connection import send_to_peer
from peer_state import num_owned_pieces
from protocol_codec import encode_message

def preferred_unchoke_iteration(state: dict, send_locks: dict[int, threading.Lock], connected: dict[int, socket.socket], 
                           logger: EventLogger, msg_types: dict) -> None:
    # Sends choke/unchoke updates to preferred neighbors 
    with state["lock"]:
        if state["stop"]:
            return
        ids = list(connected.keys())
        interested_ids = [peer_id for peer_id in ids if peer_id in state["interested_in_us"]]
        rates = dict(state["interval_bytes"])
        state["interval_bytes"] = {peer_id: 0 for peer_id in ids}
        k = state["num_preferred"]
        has_full_file = (num_owned_pieces(state["local_bitfield"], state["num_pieces"]) == state["num_pieces"])
        preferred = select_preferred_neighbors(interested_ids, rates, k, has_full_file)
        state["preferred_neighbors"] = list(preferred)

        optimistic_neigh = state.get("optimistic_neighbor")
        if optimistic_neigh is not None and optimistic_neigh not in ids:
            optimistic_neigh = None
            state["optimistic_neighbor"] = None

        to_unchoke, to_choke, unchoked = chocke_changes(ids, state["unchoked_by_us"], preferred, optimistic_neigh)
        state["unchoked_by_us"] = unchoked

    logger.log_preferred_neighbors(preferred)

    unchoke_message = encode_message(msg_types["unchoke"])
    for peer_id in to_unchoke:
        send_to_peer(send_locks, connected, peer_id, unchoke_message)

    choke_message = encode_message(msg_types["choke"])
    for peer_id in to_choke:
        send_to_peer(send_locks, connected, peer_id, choke_message)

def preferred_unchoke(interval_sec: float, state: dict, send_locks: dict[int, threading.Lock], connected: dict[int, socket.socket],
                      logger: EventLogger, msg_types: dict) -> None:
    # Runs a preferred_unchoke_iteration every interval_sec until stopped 
    while True:
        time.sleep(interval_sec)
        with state["lock"]:
            if state["stop"]:
                break
        preferred_unchoke_iteration(state, send_locks, connected, logger, msg_types)

def optimistic_unchoke_iteration(state: dict, send_locks: dict[int, threading.Lock], connected: dict[int, socket.socket],
                                 logger: EventLogger, msg_types: dict) -> None:
    # Selects 1 neighbor that is both choked and interested, and optimistically unchokes it
    chosen = None
    already_unchoked = False
    with state["lock"]:
        if state["stop"]:
            return

        choked_interested = [peer_id for peer_id in connected.keys() 
                             if peer_id in state["interested_in_us"] and peer_id not in state["unchoked_by_us"]]
        chosen = select_optimistic_neighbor(choked_interested)
        state["optimistic_neighbor"] = chosen

        if chosen is not None:
            already_unchoked = chosen in state["unchoked_by_us"]
            state["unchoked_by_us"].add(chosen)
    
    if chosen is not None:
        logger.log_optimistic_unchoke(chosen)
        if not already_unchoked:
            send_to_peer(send_locks, connected, chosen, encode_message(msg_types["unchoke"]))

def optimistic_unchoke(interval_sec: float, state: dict, send_locks: dict[int, threading.Lock],
                       connected: dict[int, socket.socket], logger: EventLogger, msg_types: dict) -> None:
    # Runs a optimistic_unchoke_iteration every interval_sec until stopped 
    while True:
        time.sleep(interval_sec)
        with state["lock"]:
            if state["stop"]:
                break
        optimistic_unchoke_iteration(state, send_locks, connected, logger, msg_types)