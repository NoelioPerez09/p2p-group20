import random 

def select_preferred_neighbors(interested_peers: list[int], download_rates: dict[int, float],
    k: int, has_complete_file: bool) -> list[int]:
    # Selects up to k peers (all of which have to be interested) 
    if k <= 0 or not interested_peers:
        return []
    
    candidates = list(interested_peers)
    
    if len(candidates) <= k:
        random.shuffle(candidates)
        return candidates
    
    if has_complete_file:
        random.shuffle(candidates)
        return candidates[:k]

    random.shuffle(candidates)
    candidates.sort(key=lambda peer_id: download_rates.get(peer_id, 0.0), reverse=True)
    return candidates[:k]

def select_optimistic_neighbor(chocked_interested_peers: list[int]) -> int | None:
    # Selects randomly a neighbor that is both chocked and interested for optimistic unchocking 
    if not chocked_interested_peers:
        return None
    return random.choice(chocked_interested_peers)

def chocke_changes(neighbor_ids: list[int], previously_unchocked: set[int], preferred_neigh: list[int], 
                          optimistic_neigh: int | None) -> tuple[list[int], list[int], set[int]]:
    # Computes which neighbors should be chocked and which ones should remain unchocked
    unchocked = set(preferred_neigh)
    if optimistic_neigh is not None:
        unchocked.add(optimistic_neigh)

    to_unchocke = []
    for peer_id in neighbor_ids:
        if peer_id in unchocked and peer_id not in previously_unchocked:
            to_unchocke.append(peer_id)

    to_chocke = []
    for peer_id in neighbor_ids:
        if peer_id not in unchocked and peer_id in previously_unchocked:
            to_chocke.append(peer_id)
    return to_unchocke, to_chocke, unchocked