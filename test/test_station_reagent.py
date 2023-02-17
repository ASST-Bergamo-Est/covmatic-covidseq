import unittest
from .common import logger
from src.covmatic_covidseq.recipe import Recipe
from src.covmatic_covidseq.stations.reagent import ReagentStation


test_recipe_1 = Recipe("Test", volume_to_distribute=10, steps=[{'name': "", "reagent": "test", "vol": 20}])
expected_vol_transferred_to_plate_1 = 15

test_recipe_2 = Recipe("Test", volume_to_distribute=5, steps=[{'name': "", "reagent": "test", "vol": 7}, {'name': "", "reagent": "test", "vol": 13}])
expected_vol_transferred_to_plate_2 = 12.5


class TestRecipeStation(unittest.TestCase):
    def setUp(self) -> None:
        self._s = ReagentStation(robot_manager_host="FAKEHOST",
                                 robot_manager_port=1234,
                                 logger=logger)

    def test_creation(self):
        self.assertTrue(self._s)

    def test_volume_to_transfer_1(self):
        self.assertEqual(expected_vol_transferred_to_plate_1, self._s.get_volume_to_transfer(test_recipe_1))

    def test_volume_to_transfer_2(self):
        self.assertEqual(expected_vol_transferred_to_plate_2, self._s.get_volume_to_transfer(test_recipe_2))
