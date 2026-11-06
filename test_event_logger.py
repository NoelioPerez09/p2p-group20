import os
import tempfile
import unittest

from event_logger import EventLogger


class TestEventLogger(unittest.TestCase):

    def setUp(self):
        '''
        creates temp folder for each test so project
        logs aren't affected
        '''
        self.test_dir = tempfile.TemporaryDirectory()
        self.old_dir = os.getcwd()
        os.chdir(self.test_dir.name)

        self.logger = EventLogger(1001)

    def tearDown(self):
        '''
        restores the original working directory and cleans up temp folder
        '''
        os.chdir(self.old_dir)
        self.test_dir.cleanup()

    def read_log(self, peer_id: int) -> list[str]:
        with open(f"log_peer_{peer_id}.log", "r") as file:
            return file.read().splitlines()

    def test_file_created(self):
        self.assertTrue(os.path.isfile("log_peer_1001.log"))

    def test_connection_made(self):
        self.logger.log_connection_made(1002)

        entry = self.read_log(1001)[0]
        self.assertTrue(
            entry.endswith("Peer 1001 makes a connection to Peer 1002.")

        )

    def test_connection_received(self):
        self.logger.log_connection_received(1002)

        entry = self.read_log(1001)[0]
        self.assertTrue(
            entry.endswith("Peer 1001 is connected from Peer 1002.")
        )

    def test_timestamp(self):
        self.logger.log_connection_made(1002)

        entry = self.read_log(1001)[0]

        #checks for date, hour, minute, and second
        pattern = r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]:"
        self.assertRegex(entry, pattern)

    def test_multiple_events(self):
        self.logger.log_connection_made(1002)
        self.logger.log_connection_received(1003)

        entries = self.read_log(1001)
        self.assertEqual(len(entries), 2)

    def test_separate_peer_logs(self):
        second_logger = EventLogger(1002)

        self.logger.log_connection_made(1002)
        second_logger.log_connection_received(1001)
        
        first_entries = self.read_log(1001)
        second_entries = self.read_log(1002)

        self.assertEqual(len(first_entries), 1)
        self.assertEqual(len(second_entries), 1)
        self.assertIn("Peer 1001 makes a connection", first_entries[0])
        self.assertIn("Peer 1002 is connected from", second_entries[0])


    def test_remaining_log_events(self):
        '''
        test the new logging messages
        '''
        logger = EventLogger(9999)

        logger.log_preferred_neighbors([1001, 1002])
        logger.log_optimistic_unchoke(1003)
        logger.log_unchoked(1001)
        logger.log_choked(1002)
        logger.log_have(1001, 5)
        logger.log_interested(1002)
        logger.log_not_interested(1003)
        logger.log_piece_downloaded(1001, 5, 10)
        logger.log_download_complete()

        with open(logger.file_path, "r") as file:
            lines = file.readlines()

        expected = [
            "Peer 9999 has the preferred neighbors 1001, 1002.",
            "Peer 9999 has the optimistically unchoked neighbor 1003.",
            "Peer 9999 is unchoked by 1001.",
            "Peer 9999 is choked by 1002.",
            "Peer 9999 received the 'have' message from 1001 for the piece 5.",
            "Peer 9999 received the 'interested' message from 1002.",
            "Peer 9999 received the 'not interested' message from 1003.",
            "Peer 9999 has downloaded the piece 5 from 1001. Now the number of pieces it has is 10.",
            "Peer 9999 has downloaded the complete file."
        ]

        self.assertEqual(len(lines[-9:]), 9)

        for line, message in zip(lines[-9:], expected):
            self.assertEqual(line.split("]: ", 1)[1].strip(), message)


if __name__ == "__main__":
    unittest.main()
                         
