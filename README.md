
# P2P File Sharing Project - Group 20

## Group Members
- Anish Gaonkar
- Noelio Perez
- Paapa Kusi

## Midpoint Progress

So far, our group has implemented the following components of the P2P file sharing system:

- **TCP Connection Management:** Implemented incoming and outgoing TCP connections between multiple peers using sockets.
- **Handshake Protocol:** Implemented 32-byte handshake exchanges to identify and validate connected peers.
- **Configuration Parsing:** Implemented parsing for `Common.cfg` and `PeerInfo.cfg` to load peer information and project settings.
- **Event Logging:** Implemented logging for peer connection events, including timestamps and peer IDs.
- **Peer Process Integration:** Integrated TCP connections, handshakes, configuration parsing, and logging into `peerProcess.py`.
- **Testing:** Created unit tests and integration tests to verify the functionality of these components.

## Current Status

We successfully tested three peer processes (1001, 1002, and 1003) connecting over TCP, exchanging handshakes, and generating the expected connection logs.

Our group developed 34 automated tests covering TCP connections, handshakes, event logging, and integration. All 34 tests passed during midpoint verification.

File transfer and choking/unchoking functionality will be implemented for the final submission.
