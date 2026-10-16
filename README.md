
# P2P File Sharing Project - Group 20

## Group Members
- Anish Gaonkar
- Noelio Perez
- Paapa Kusi

## Midpoint Progress

So far, our group has implemented the following components of the P2P file sharing system:

- **TCP Connection Management:** Implemented TCP connections between multiple peers using sockets.
- **Handshake Protocol:** Implemented handshake exchange for connected peer validation and identification.
- **Configuration Parsing:** Implemented parsing for `Common.cfg` and `PeerInfo.cfg`. 
- **Event Logging:** Implemented event logger for peer connection, with timestamps and respective peer IDs.
- **Peer Process Integration:** Integrated connections, handshakes, configuration parsing, and logging into `peer_process.py`.
- **Testing:** Created unit tests and integration tests to verify the functionality of these components.

## Current Status

We successfully tested three peer processes (1001, 1002, and 1003) connecting over TCP, exchanging handshakes, and generating the expected connection logs.

A 34 automated tests were developed that included TCP connection, handshake, the event logger, and overall integration. All 34 tests passed. 

Actual file transfer (including choking/unchoking functionality) is yet to be implemented, but will be implemented for the final submission. 
