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

        #Check for date, hour, minute, and second
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

        # each pair should only record its own events
        first_entries = self.read_log(1001)
        second_entries = self.read_log(1002)

        self.assertEqual(len(first_entries), 1)
        self.assertEqual(len(second_entries), 1)
        self.assertIn("Peer 1001 makes a connection", first_entries[0])
        self.assertIn("Peer 1002 is connected from", second_entries[0])

if __name__ == "__main__":
    unittest.main()
                         