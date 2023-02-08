import logging
import unittest

from src.covmatic_covidseq.stations.reagent import ReagentStation


class TestRecipeStation(unittest.TestCase):
    def setUp(self) -> None:
        self._s = ReagentStation(robot_manager_host="FAKEHOST",
                                 robot_manager_port=1234,
                                 logger=logging.getLogger())

    def test_creation(self):
        self.assertTrue(self._s)
