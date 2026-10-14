import socket
import sys

from config import parse_common_config, parse_peer_info
from event_logger import EventLogger
from handshake import perform_handshake, perform_incoming_handshake
from tcp import ConnectionManager


def connect_to_earlier_peers(manager: ConnectionManager, logger: EventLogger) -> dict[int, socket.socket]:
    '''
    Opens a TCP connection to every peer listed before this one in
    PeerInfo.cfg, handshakes with each of them, and logs the connection.
    Returns a dictionary of peer_id -> connected socket
    '''
    #the later peer always initiates, so dial every earlier peer
    outgoing = manager.connect_to_previous()

    for expected_id, connection in outgoing.items():
        #a silent peer shouldn't be able to block the handshake forever
        connection.settimeout(manager.timeout)
        perform_handshake(connection, manager.peer_id, expected_id)
        connection.settimeout(None)

        logger.log_connection_made(expected_id)

    return outgoing


def accept_later_peers(manager: ConnectionManager, logger: EventLogger, connected: dict[int, socket.socket]):
    '''
    Accepts one connection from every peer listed after this one in
    PeerInfo.cfg. We can't know who is calling until their handshake
    arrives, so we read it first and then check the ID.
    Adds each accepted peer to connected (peer_id -> connected socket)
    '''
    allowed = {p["peer_id"] for p in manager.later_peers}

    for _ in allowed:
        #later peers are started by hand, so keep waiting after an accept timeout
        while True:
            try:
                connection = manager.accept_next()
                break
            except socket.timeout:
                continue

        #handshake, only accepting peers that haven't connected yet
        connection.settimeout(manager.timeout)
        other_id = perform_incoming_handshake(connection, manager.peer_id, allowed - set(connected))
        connection.settimeout(None)

        connected[other_id] = connection
        logger.log_connection_received(other_id)


def main():
    '''
    Entry point for one peer.
    Usage: python peerProcess.py <peer_id> [peer_info_path]
    '''
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python peerProcess.py <peer_id> [peer_info_path]")

    try:
        peer_id = int(sys.argv[1])
    except ValueError:
        sys.exit("Peer ID must be an integer!")

    #optional second argument lets us test locally without editing PeerInfo.cfg
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
        #listen before connecting so later peers can reach us right away
        manager.start_listening()

        connected = connect_to_earlier_peers(manager, logger)
        accept_later_peers(manager, logger, connected)

        #every other peer in the file should now be connected to us
        if len(connected) != len(all_peers) - 1:
            raise ValueError("Incomplete mesh")

        print(f"Peer {peer_id} connected to peers {sorted(connected)}")

        #the message loop and choke/unchoke timers will start here in the final

    except (OSError, EOFError, ValueError) as error:
        print(f"Peer {peer_id} failed: {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        manager.close()


if __name__ == "__main__":
    main()
