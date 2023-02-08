import logging
import unittest

from src.covmatic_covidseq.recipe import Recipe
from src.covmatic_covidseq.station import CovidseqBaseStation

RECIPE_1_NAME = "TEST RECIPE 1"
RECIPE_1 = Recipe()


class CovidseqTestStation(CovidseqBaseStation):
    def _tipracks(self):
        pass


class BaseSetup(unittest.TestCase):
    ''' Base setup for test case. Please do not put tests in this class. '''
    def setUp(self):
        self._s = CovidseqTestStation(robot_manager_host="FAKEHOST",
                                      robot_manager_port=1234,
                                      ot_name="TEST",
                                      logger=logging.getLogger())


class TestRecipes(BaseSetup):
    def test_recipe_is_empty(self):
        self.assertEqual(0, len(self._s._recipes))

    def test_add_recipe_1_is_added(self):
        self._s.add_recipe(RECIPE_1_NAME, RECIPE_1)
        self.assertEqual(1, len(self._s._recipes))

    def test_get_recipe_1(self):
        self._s.add_recipe(RECIPE_1_NAME, RECIPE_1)
        self.assertTrue(self._s.get_recipe(RECIPE_1_NAME))

    def test_get_recipe_1_value(self):
        self._s.add_recipe(RECIPE_1_NAME, RECIPE_1)
        self.assertEqual(RECIPE_1, self._s.get_recipe(RECIPE_1_NAME))

