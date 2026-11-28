import socket
import sys
import threading

from config import parse_common_config, parse_peer_info
from event_logger import EventLogger
from handshake import perform_handshake, perform_incoming_handshake
from tcp import ConnectionManager
from peer_state import num_owned_pieces
from config import get_self_info
from peer_state import create_initial_bitfield
from protocol_codec import message_type
from message_io import exchange_bitfield_interest
from message_io import recv_framed_message
import struct
from peer_state import set_piece, is_interested_in
from protocol_codec import encode_message
from piece_transfer import pick_missing_piece, send_piece_request
from piece_transfer import handle_piece_request
from piece_transfer import handle_piece_received
from protocol_codec import encode_havereq_message

from unchoking_timers import preferred_unchoke_iteration, optimistic_unchoke_iteration
import time
from completion import all_complete_file, shutdown_peer
from peer_connection import send_to_peer, send_messages, QueuedConnection


def connect_to_earlier_peers(manager: ConnectionManager, logger: EventLogger) -> dict[int, socket.socket]:
    '''
    Opens a connection to every peer listed before this peerg, then handshakes
    with each pear, and lastly logs the connection.
    Returns a dic of [peer_id, connected socket].
    '''
    outgoing = manager.connect_to_previous()

    for expected_id, connection in outgoing.items():
        #timeout for silent peer
        connection.settimeout(manager.timeout)
        perform_handshake(connection, manager.peer_id, expected_id)
        connection.settimeout(None)

        logger.log_connection_made(expected_id)

    return outgoing


def accept_later_peers(manager: ConnectionManager, logger: EventLogger, connected: dict[int, socket.socket]):
    '''
    Accepts a connection from every peer listed after this peer.
    Reads it first and then check the ID.
    Adds each accepted peer to connected dict
    '''
    allowed = {p["peer_id"] for p in manager.later_peers}

    for _ in allowed:
         #keep waiting after an accept timeout
        while True:
            try:
                connection = manager.accept_next()
                break
            except socket.timeout:
                continue

        #handshake, this only accepts peers who haven't connected yet
        connection.settimeout(manager.timeout)
        other_id = perform_incoming_handshake(connection, manager.peer_id, allowed - set(connected))
        connection.settimeout(None)

        connected[other_id] = connection
        logger.log_connection_received(other_id)

def handle_interest_message(msg_type, neigh_id, interested_peers, logger):
    '''
    updates whether a neighbor is interested in our pieces
    and logs the received message
    '''
    if msg_type == message_type["interested"]:
        interested_peers.add(neigh_id)
        logger.log_interested(neigh_id)

    elif msg_type == message_type["not_interested"]:
        interested_peers.discard(neigh_id)
        logger.log_not_interested(neigh_id)

def handle_choke_message(msg_type, neigh_id, unchoked_by,
                         pending_requests, logger):
    '''
    updates whether we can request pieces from a neighbor
    '''
    if msg_type == message_type["choke"]:
        unchoked_by.discard(neigh_id)

        #remove outstanding requests from this neighbor
        for piece_index, requested_peer in list(pending_requests.items()):
            if requested_peer == neigh_id:
                del pending_requests[piece_index]

        logger.log_choked(neigh_id)

    elif msg_type == message_type["unchoke"]:
        unchoked_by.add(neigh_id)
        logger.log_unchoked(neigh_id)

def handle_have_message(connection, payload, neigh_id,
                        local_bitfield, neigh_bitfields,
                        num_pieces, logger):
    '''
    updates the neighbor's bitfield and sends our interest
    based on the pieces we still need
    '''
    #validate the payload and piece index
    if len(payload) != 4:
        return

    piece_index = struct.unpack(">I", payload)[0]

    if piece_index >= num_pieces:
        return

    #initialize neighbor bitfield if necessary
    if neigh_id not in neigh_bitfields:
        neigh_bitfields[neigh_id] = bytearray((num_pieces + 7) // 8)

    #update the neighbor's piece ownership
    set_piece(neigh_bitfields[neigh_id], piece_index)
    logger.log_have(neigh_id, piece_index)

    #check if the neighbor has any pieces we still need
    if is_interested_in(local_bitfield,
                        neigh_bitfields[neigh_id], num_pieces):
        reply = encode_message(message_type["interested"])
    else:
        reply = encode_message(message_type["not_interested"])

    connection.sendall(reply)

def request_next_piece(connection, neigh_id, local_bitfield,
                       neigh_bitfields, pending_requests,
                       unchoked_by, num_pieces):
    '''
    requests a missing piece from an available neighbor
    '''
    #check if the neighbor allows us to download
    if neigh_id not in unchoked_by:
        return

    if neigh_id not in neigh_bitfields:
        return

    #allow only one outstanding request per neighbor
    if neigh_id in pending_requests.values():
        return

    #select a missing piece that is not already requested
    piece_index = pick_missing_piece(
        local_bitfield,
        neigh_bitfields[neigh_id],
        pending_requests,
        num_pieces
    )

    #no available pieces to request
    if piece_index is None:
        return

    #send request and track the pending piece
    send_piece_request(
        connection,
        neigh_id,
        piece_index,
        pending_requests,
        message_type
    )

def process_piece_request(connection, payload, peer_id,
                          neigh_id, common_config,
                          local_bitfield, unchoked_peers):
    '''
    handles a neighbor's request for a file piece
    '''
    #ignore requests from neighbors we have choked
    if neigh_id not in unchoked_peers:
        return

    #validate the requested piece index
    if len(payload) != 4:
        return

    piece_index = struct.unpack(">I", payload)[0]

    if piece_index >= common_config["NumberOfPieces"]:
        return

    #read and send the requested piece
    handle_piece_request(
        connection,
        payload,
        peer_id,
        common_config["FileName"],
        common_config["FileSize"],
        common_config["PieceSize"],
        local_bitfield,
        neigh_id in unchoked_peers
    )

def process_piece_received(payload, peer_id, neigh_id,
                           common_config, local_bitfield,
                           pending_requests, download_rates,
                           connected, logger):
    '''
    stores received pieces, updates download rates,
    and notifies neighbors of newly downloaded pieces
    '''
    #validate the received piece
    if len(payload) < 4:
        return

    piece_index = struct.unpack(">I", payload[:4])[0]

    if piece_index >= common_config["NumberOfPieces"]:
        return

    #check that the received piece has the correct size
    piece_size = common_config["PieceSize"]
    expected_size = min(
        piece_size,
        common_config["FileSize"] - piece_index * piece_size
    )

    if len(payload) - 4 != expected_size:
        return

    #store the piece and update our bitfield
    result = handle_piece_received(
        payload,
        peer_id,
        neigh_id,
        common_config["FileName"],
        common_config["FileSize"],
        common_config["PieceSize"],
        local_bitfield,
        pending_requests
    )

    if result is None:
        return

    piece_index, owned_count = result

    #update the neighbor's download statistics
    download_rates[neigh_id] = (
        download_rates.get(neigh_id, 0) + len(payload) - 4
    )

    #log the downloaded piece
    logger.log_piece_downloaded(
        neigh_id, piece_index, owned_count
    )

    #notify all connected neighbors about the new piece
    have_msg = encode_havereq_message(
        message_type["have"], piece_index
    )

    for connection in connected.values():
        connection.sendall(have_msg)

    #log when this peer finishes downloading the file
    if owned_count == common_config["NumberOfPieces"]:
        logger.log_download_complete()

def update_neighbor_interest(connected, local_bitfield,
                             neigh_bitfields, num_pieces):
    '''
    reevaluates our interest in each connected neighbor
    '''
    for neigh_id, connection in connected.items():
        if neigh_id not in neigh_bitfields:
            continue

        #check if the neighbor has pieces we still need
        interested = is_interested_in(
            local_bitfield,
            neigh_bitfields[neigh_id],
            num_pieces
        )

        #send the updated interest status
        if interested:
            msg = encode_message(message_type["interested"])
        else:
            msg = encode_message(message_type["not_interested"])

        connection.sendall(msg)

def dispatch_control_message(msg_type, payload, connection,
                             neigh_id, local_bitfield,
                             neigh_bitfields, interested_peers,
                             unchoked_by, pending_requests,
                             num_pieces, logger):
    '''
    processes incoming interest, choke, and have messages
    '''
    if msg_type in (
        message_type["interested"],
        message_type["not_interested"]
    ):
        handle_interest_message(
            msg_type, neigh_id, interested_peers, logger
        )

    elif msg_type in (
        message_type["choke"],
        message_type["unchoke"]
    ):
        handle_choke_message(
            msg_type, neigh_id, unchoked_by,
            pending_requests, logger
        )

    elif msg_type == message_type["have"]:
        handle_have_message(
            connection, payload, neigh_id,
            local_bitfield, neigh_bitfields,
            num_pieces, logger
        )

    else:
        return False

    return True

def receive_messages(connection, neigh_id, peer_id,
                     common_config, local_bitfield,
                     neigh_bitfields, interested_peers,
                     unchoked_peers, unchoked_by,
                     pending_requests, download_rates,
                     connected, logger, state_lock,
                     stop_event):
    '''
    continuously receives and processes messages from a neighbor
    and cleans up its state after disconnection
    '''
    num_pieces = common_config["NumberOfPieces"]

    try:
        while not stop_event.is_set():
            #receive messages without holding the state lock
            msg_type, payload = recv_framed_message(connection)

            with state_lock:
                #handle interest, choke, unchoke, and have messages
                handled = dispatch_control_message(
                    msg_type, payload, connection,
                    neigh_id, local_bitfield,
                    neigh_bitfields, interested_peers,
                    unchoked_by, pending_requests,
                    num_pieces, logger
                )

                if handled:
                    request_next_piece(
                        connection, neigh_id, local_bitfield,
                        neigh_bitfields, pending_requests,
                        unchoked_by, num_pieces
                    )

                elif msg_type == message_type["request"]:
                    #send the requested piece to the neighbor
                    process_piece_request(
                        connection,
                        payload,
                        peer_id,
                        neigh_id,
                        common_config,
                        local_bitfield,
                        unchoked_peers
                    )

                elif msg_type == message_type["piece"]:
                    #store the received piece
                    process_piece_received(
                        payload,
                        peer_id,
                        neigh_id,
                        common_config,
                        local_bitfield,
                        pending_requests,
                        download_rates,
                        connected,
                        logger
                    )

                    #update our interest in all neighbors
                    update_neighbor_interest(
                        connected,
                        local_bitfield,
                        neigh_bitfields,
                        num_pieces
                    )

                    #continue requesting missing pieces
                    for other_id, other_conn in connected.items():
                        request_next_piece(
                            other_conn,
                            other_id,
                            local_bitfield,
                            neigh_bitfields,
                            pending_requests,
                            unchoked_by,
                            num_pieces
                        )

    except (OSError, EOFError, ConnectionError) as error:
        with state_lock:
            #check if the disconnected neighbor completed its download
            neighbor_complete = (
                neigh_id in neigh_bitfields
                and num_owned_pieces(
                    neigh_bitfields[neigh_id], num_pieces
                ) == num_pieces
            )

        if not stop_event.is_set() and not neighbor_complete:
            print(f"Connection error with peer {neigh_id}: {error}")
    finally:
        #clean up neighbor state after disconnection
        with state_lock:
            interested_peers.discard(neigh_id)
            unchoked_peers.discard(neigh_id)
            unchoked_by.discard(neigh_id)

            #release outstanding requests from this neighbor
            for piece_index, requested_peer in list(
                pending_requests.items()
            ):
                if requested_peer == neigh_id:
                    del pending_requests[piece_index]

            download_rates.pop(neigh_id, None)
            connected.pop(neigh_id, None)

        connection.close()

def run_unchoking_scheduler(state, send_locks, connected,
                            logger, common_config, stop_event):
    '''
    runs preferred and optimistic unchoking at their
    configured intervals
    '''
    preferred_interval = common_config["UnchokingInterval"]
    optimistic_interval = common_config["OptimisticUnchokingInterval"]

    next_preferred = time.monotonic() + preferred_interval
    next_optimistic = time.monotonic() + optimistic_interval

    while not stop_event.is_set():
        now = time.monotonic()

        #update preferred neighbors
        if now >= next_preferred:
            preferred_unchoke_iteration(
                state, send_locks, connected,
                logger, message_type
            )
            next_preferred = now + preferred_interval

        #update optimistic neighbor
        if now >= next_optimistic:
            optimistic_unchoke_iteration(
                state, send_locks, connected,
                logger, message_type
            )
            next_optimistic = now + optimistic_interval

        stop_event.wait(0.1)
        
def main():
    '''
    Entry point for one peer.
    Usage: python3 peer_process.py <peer_id> [peer_info_path]
    '''
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python3 peer_process.py <peer_id> [peer_info_path]]")

    try:
        peer_id = int(sys.argv[1])
    except ValueError:
        sys.exit("Peer ID must be an integer!")

    #optional second argument for testing locally
    peer_info_path = sys.argv[2] if len(sys.argv) == 3 else "PeerInfo.cfg"

    common_config = parse_common_config()
    all_peers = parse_peer_info(peer_info_path)
    print(f"Peer {peer_id} loaded config: {common_config}")

    try:
        manager = ConnectionManager(peer_id, all_peers)
    except ValueError as error:
        sys.exit(f"Invalid configuration: {error}")

    logger = EventLogger(peer_id)

    #get file info and initial ownership for this peer
    self_info = get_self_info(peer_id, all_peers)
    num_pieces = common_config["NumberOfPieces"]
    has_file = self_info["has_file"]

    #initialize our bitfield based on whether we have the file
    local_bitfield = create_initial_bitfield(num_pieces, has_file)

    #keep track of neighbor pieces and requested pieces
    neigh_bitfields = {}
    pending_requests = {}

    #track interest and choking in both directions
    interested_peers = set()
    unchoked_peers = set()
    unchoked_by = set()

    #bytes downloaded from each neighbor during an interval
    download_rates = {}
    state_lock = threading.Lock()

    stop_event = threading.Event()
    send_locks = {}
    threads = []

    #shared runtime state for message handling and scheduling
    state = {
        "lock": state_lock,
        "peer_id": peer_id,
        "num_pieces": num_pieces,
        "local_bitfield": local_bitfield,
        "neigh_bitfields": neigh_bitfields,
        "interested_in_us": interested_peers,
        "unchoked_by_us": unchoked_peers,
        "interval_bytes": download_rates,
        "num_preferred": common_config["NumberOfPreferredNeighbors"],
        "preferred_neighbors": [],
        "optimistic_neighbor": None,
        "logged_complete": has_file,
        "stop": False
    }
    connected = {}
    try:
        manager.start_listening()

        connected = connect_to_earlier_peers(manager, logger)
        accept_later_peers(manager, logger, connected)

        #every other peer in the file should be connected to this peer by now
        if len(connected) != len(all_peers) - 1:
            raise ValueError("Incomplete mesh")

        print(f"Peer {peer_id} connected to peers {sorted(connected)}")

        #exchange bitfields and interest messages with each neighbor
        for neigh_id, connection in connected.items():
            connection.settimeout(manager.timeout)

            peer_interested = exchange_bitfield_interest(
                connection,
                peer_id,
                neigh_id,
                local_bitfield,
                neigh_bitfields,
                num_pieces,
                has_file,
                message_type
            )

            connection.settimeout(None)

            #track and log the neighbor's interest
            if peer_interested:
                interested_peers.add(neigh_id)
                logger.log_interested(neigh_id)
            else:
                logger.log_not_interested(neigh_id)

        #initialize outgoing message queues and sender threads
        for neigh_id, connection in list(connected.items()):
            queued_connection = QueuedConnection(connection)
            connected[neigh_id] = queued_connection
            send_locks[neigh_id] = threading.Lock()

            sender_thread = threading.Thread(
                target=send_messages,
                args=(
                    connection,
                    queued_connection.outgoing,
                    stop_event
                ),
                daemon=True
            )

            threads.append(sender_thread)
            sender_thread.start()

        #initialize receiver threads for each connected neighbor
        for neigh_id, connection in list(connected.items()):
            receiver_thread = threading.Thread(
                target=receive_messages,
                args=(
                    connection,
                    neigh_id,
                    peer_id,
                    common_config,
                    local_bitfield,
                    neigh_bitfields,
                    interested_peers,
                    unchoked_peers,
                    unchoked_by,
                    pending_requests,
                    download_rates,
                    connected,
                    logger,
                    state_lock,
                    stop_event
                ),
                daemon=True
            )

            threads.append(receiver_thread)
            receiver_thread.start()


        #start the unchoking scheduler
        scheduler_thread = threading.Thread(
            target=run_unchoking_scheduler,
            args=(
                state,
                send_locks,
                connected,
                logger,
                common_config,
                stop_event
            ),
            daemon=True
        )

        threads.append(scheduler_thread)
        scheduler_thread.start()


        #get the IDs of all peers in the configuration
        all_peer_ids = [p["peer_id"] for p in all_peers]

        #wait until every peer has downloaded the complete file
        while not stop_event.is_set():
            if all_complete_file(state, all_peer_ids):
                print(f"All peers have completed downloading the file.")
                break

            stop_event.wait(0.5)

    except (OSError, EOFError, ValueError) as error:
        print(f"Peer {peer_id} failed: {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        #stop scheduling new choking updates
        with state_lock:
            state["stop"] = True

        #allow queued messages to finish sending
        deadline = time.monotonic() + 5

        with state_lock:
            connections = list(connected.values())

        while time.monotonic() < deadline:
            if all(
                connection.outgoing.unfinished_tasks == 0
                for connection in connections
                if isinstance(connection, QueuedConnection)
            ):
                break

            time.sleep(0.1)

        #stop workers and close connections
        stop_event.set()
        shutdown_peer(
            state, send_locks, connected,
            manager, threads
        )


if __name__ == "__main__":
    main()
