import sys

#keys Common.cfg must contain, and which of them must be integers
COMMON_INT_KEYS = ["NumberOfPreferredNeighbors", "UnchokingInterval",
                   "OptimisticUnchokingInterval", "FileSize", "PieceSize"]
COMMON_KEYS = COMMON_INT_KEYS + ["FileName"]

def parse_common_config(path : str ="Common.cfg") -> dict:
    '''
    Reads Common.cfg and returns it as a dictionary,
    exits with a clear message if the file is missing or invalid
    '''
    config_dict = dict()
    try:
        with open(path, "r") as file:
            for line in file:
                curr_line = line.strip().split()
                if not curr_line:
                    continue
                if len(curr_line) != 2:
                    sys.exit(f"Invalid common config line: '{line.strip()}'")
                if curr_line[1].isnumeric():
                    config_dict[curr_line[0]] = int(curr_line[1])
                else:
                    config_dict[curr_line[0]] = curr_line[1]
    except FileNotFoundError:
        sys.exit(f"Could not find {path}")

    #every required key must be present
    for key in COMMON_KEYS:
        if key not in config_dict:
            sys.exit(f"{path} is missing {key}")

    #numeric keys must actually be numbers
    for key in COMMON_INT_KEYS:
        if not isinstance(config_dict[key], int):
            sys.exit(f"{key} must be a whole number")

    for key in ["UnchokingInterval", "OptimisticUnchokingInterval", "FileSize", "PieceSize"]:
        if config_dict[key] <= 0:
            sys.exit(f"{key} must be greater than 0")

    config_dict["NumberOfPieces"] = (config_dict["FileSize"] + config_dict["PieceSize"] - 1) // config_dict["PieceSize"]
    return config_dict

def parse_peer_info(path : str ="PeerInfo.cfg") -> list[dict]:
    '''
    Read PeerInfo.cfg and returns it as a list of dictionaries,
    where each dictionary is a peer info line
    '''
    config_list = []
    seen_ids = set()
    try:
        with open(path, "r") as file:
            for line in file:
                curr_line = line.strip().split()

                if not curr_line:
                    continue
                if len(curr_line) != 4:
                    sys.exit(f"Invalid peer info line: '{line.strip()}'")
                try:
                    peer_id = int(curr_line[0])
                    port = int(curr_line[2])
                    has_file = int(curr_line[3])
                except ValueError:
                    sys.exit(f"Invalid peer info line: '{line.strip()}'")
                if peer_id <= 0:
                    sys.exit(f"Peer ID must be positive: {peer_id}")
                if peer_id in seen_ids:
                    sys.exit(f"Duplicate peer ID in {path}: {peer_id}")
                if not 1 <= port <= 65535:
                    sys.exit(f"Invalid port for peer {peer_id}: {port}")
                if has_file not in (0, 1):
                    sys.exit(f"has_file must be 0 or 1 for peer {peer_id}")
                seen_ids.add(peer_id)
                curr_dict = dict()
                curr_dict["peer_id"] = peer_id
                curr_dict["host"] = curr_line[1]
                curr_dict["port"] = port
                curr_dict["has_file"] = bool(has_file)
                config_list.append(curr_dict)
    except FileNotFoundError:
        sys.exit(f"Could not find {path}")

    if not config_list:
        sys.exit(f"{path} contains no peers")
    return config_list

def peers_before(peer_id: int, all_peers: list[dict]) -> list[dict]:
    '''
    Returns the sublist of peers that appear
    before peer_id in the file.
    Raises ValueError if peer_id isn't in the file
    '''
    peers = []
    for p in all_peers:
        if p['peer_id'] == peer_id:
            return peers
        peers.append(p)
    raise ValueError(f"Peer {peer_id} is not in the peer info file")

def get_self_info(peer_id: int, all_peers: list[dict]) -> dict:
    '''
    Returns this peer's own record from parse_peer_info() list[dict].
    Raises ValueError if peer_id isn't in the file
    '''
    for p in all_peers:
        if p['peer_id'] == peer_id:
            return p
    raise ValueError(f"Peer {peer_id} is not in the peer info file")

def print_config(common_config: dict, all_peers: list[dict]):
    '''
    Prints the parsed configuration
    '''
    print("Common config:")
    for key, value in common_config.items():
        print(f"  {key}: {value}")
    print("Peers (in file order):")
    for p in all_peers:
        print(f"  {p['peer_id']} {p['host']}:{p['port']} has_file={p['has_file']}")

if __name__ == "__main__":
    print_config(parse_common_config(), parse_peer_info())
