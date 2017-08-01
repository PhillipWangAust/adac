import unittest
import os
import tempfile
import adac.data_collector as dc


class TestCollectorApp(unittest.TestCase):


    def setUp(self):
        self.db_fd, self.db_name = tempfile.mkstemp()
        dc.DB = dc.set_db(self.db_name)
        self.app = dc.APP.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_name)

    def test_logs(self):
        pass

