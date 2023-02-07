import unittest
from src.covmatic_covidseq.station import CovidseqBaseStation


class CovidseqTestStation(CovidseqBaseStation):
    def _tipracks(self):
        pass


class BaseClassInstance(unittest.TestCase):
    def setUp(self):
        self._station = CovidseqTestStation(robot_manager_host="FAKEHOST", robot_manager_port=1234, ot_name="TEST")

    def test_recipe_is_empty(self):
        self.assertEqual(0, len(self._station._recipes))
