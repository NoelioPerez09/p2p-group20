import socket
import unittest
import threading

from protocol_codec import encode_handshake

from handshake import perform_handshake

class TestHandshake(unittest.TestCase):

    def test_valid_handshake(self):
        '''
        Checks that two peers can successfully
        exchange and validate their handshakes
        '''

        sock1, sock2 = socket.socketpair()
        try:
            #simulate peer 1002 sending a handshake
            sock2.sendall(
                __import__("protocol_codec").encode_handshake(1002)
            )

            #peer 1001 performs handshake with peer 1002
            result = perform_handshake(sock1, 1001, 1002)

            self.assertEqual(result, 1002)
        finally:
            sock1.close()
            sock2.close()

    def test_two_way_handshake(self):
        '''
        checks that both peers can exhcange and validate handshales
        '''
        sock1, sock2 = socket.socketpair()
        results = {}
        errors = []

        def run_peer(sock, peer_id, expected_id):
            try:
                results[peer_id] = perform_handshake(
                    sock, peer_id, expected_id
                )
            except Exception as error:
                errors.append(error)
            finally:
                sock.close()

        #Each thread represents a separate peer
        thread1 = threading.Thread(
            target = run_peer, args=(sock1, 1001, 1002)
        )
        thread2= threading.Thread(
            target = run_peer, args=(sock2, 1002, 1001)
        )
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        self.assertEqual(errors, [])
        self.assertEqual(results[1001], 1002)
        self.assertEqual(results[1002], 1001)

    def test_wrong_peer_id(self):
        '''
        Checks that an unexpected peer ID is rejected
        '''
        sock1, sock2 = socket.socketpair()

        try:
            #peer 1003 connects, but expecting 1002
            sock2.sendall(encode_handshake(1003))

            with self.assertRaises(ValueError):
                perform_handshake(sock1, 1001, 1002)
        finally:
            sock1.close()
            sock2.close()

    def test_incomplete_handshake(self):
        '''
        Checks that a connection closing before all
        32 handshake bytes are received raises an error
        '''
        sock1, sock2 = socket.socketpair()

        try:
            #send only pare of the 32-byte handshale
            sock2.sendall(encode_handshake(1002)[:15])

            #stop sending (but stay connected) before the rest of the handshake
            sock2.shutdown(socket.SHUT_WR)

            with self.assertRaises(EOFError):
                perform_handshake(sock1, 1001, 1002)
        finally:
            sock1.close()
            sock2.close()

if __name__ == "__main__":
    unittest.main()

