import logging
import unittest

from src.covmatic_covidseq.station import NUM_SAMPLES_MAX
from src.covmatic_covidseq.recipe import Recipe
from .common import CovidseqTestStation

RECIPE_1_NAME = "TEST RECIPE 1"
RECIPE_1 = Recipe(RECIPE_1_NAME)


class BaseSetup(unittest.TestCase):
    ''' Base setup for test case. Please do not put tests in this class. '''
    def setUp(self):
        self._s = CovidseqTestStation(robot_manager_host="FAKEHOST",
                                      robot_manager_port=1234,
                                      ot_name="TEST",
                                      recipe_file=None,
                                      logger=logging.getLogger())


class TestRecipes(BaseSetup):
    def test_recipe_is_empty(self):
        self.assertEqual(0, len(self._s._recipes))

    def test_add_recipe_1_is_added(self):
        self._s.add_recipe(RECIPE_1)
        self.assertEqual(1, len(self._s._recipes))

    def test_get_recipe_1(self):
        self._s.add_recipe(RECIPE_1)
        self.assertTrue(self._s.get_recipe(RECIPE_1_NAME))

    def test_get_recipe_1_value(self):
        self._s.add_recipe(RECIPE_1)
        self.assertEqual(RECIPE_1, self._s.get_recipe(RECIPE_1_NAME))


class TestWithLoadRecipes(unittest.TestCase):
    def setUp(self):
        self._s = CovidseqTestStation(robot_manager_host="FAKEHOST",
                                      robot_manager_port=1234,
                                      ot_name="TEST",
                                      logger=logging.getLogger())

    def test_recipes_load(self):
        self.assertGreater(len(self._s._recipes), 0)

class TestNumSamples(unittest.TestCase):
    def test_num_samples_ok(self):
        s = CovidseqTestStation(robot_manager_host="FAKEHOST",
                                robot_manager_port=1234,
                                ot_name="TEST",
                                logger=logging.getLogger(),
                                num_samples=NUM_SAMPLES_MAX)
        self.assertTrue(s)

    def test_num_samples_too_much(self):
        with self.assertRaises(Exception):
            s = CovidseqTestStation(robot_manager_host="FAKEHOST",
                                    robot_manager_port=1234,
                                    ot_name="TEST",
                                    logger=logging.getLogger(),
                                    num_samples=NUM_SAMPLES_MAX+1)
