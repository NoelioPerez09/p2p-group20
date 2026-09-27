import math
import sys

def parse_common_config(path="Common.cfg"):
    '''
    Reads Common.cfg and returns it as a dictionary
    '''
    config_dict = dict()
    with open(path, "r") as file:
        for line in file:
            curr_line = line.strip().split()
            if len(curr_line) != 2:
                sys.exit("Invalid common config file!")
            if curr_line[1].isnumeric():
                config_dict[curr_line[0]] = int(curr_line[1])
            else:
                config_dict[curr_line[0]] = curr_line[1]
    config_dict["NumberOfPieces"] = math.ceil(config_dict["FileSize"] / config_dict["PieceSize"])
    return config_dict

def parse_peer_info(path="PeerInfo.cfg"):
    '''
    Read PeerInfo.cfg and returns it as a list of dictionaries,
    where each dictionary is a peer info line
    '''
    config_list = []
    with open(path, "r") as file:
            for line in file:
                curr_line = line.strip().split()
                if len(curr_line) != 4:
                    sys.exit("Invalid peer info config file!")
                curr_dict = dict()
                curr_dict["peer_id"] = int(curr_line[0])
                curr_dict["host"] = curr_line[1]
                curr_dict["port"] = curr_line[2]
                curr_dict["has_file"] = bool(int(curr_line[3]))
                config_list.append(curr_dict)
    return config_list

def peers_before(peer_id, all_peers):
    '''
    Returns the sublist of peers that appear 
    before peer_id in the file
    '''
    pass