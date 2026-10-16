import socket
import sys

from config import parse_common_config, parse_peer_info
from event_logger import EventLogger
from handshake import perform_handshake, perform_incoming_handshake
from tcp import ConnectionManager


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

    try:
        manager.start_listening()

        connected = connect_to_earlier_peers(manager, logger)
        accept_later_peers(manager, logger, connected)

        #every other peer in the file should be connected to this peer by now
        if len(connected) != len(all_peers) - 1:
            raise ValueError("Incomplete mesh")

        print(f"Peer {peer_id} connected to peers {sorted(connected)}")

        #TODO: Continue connection after handshake (will be implemented in final)

    except (OSError, EOFError, ValueError) as error:
        print(f"Peer {peer_id} failed: {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        manager.close()


if __name__ == "__main__":
    main()
