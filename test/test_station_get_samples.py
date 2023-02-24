import logging
import unittest
from unittest import mock

from src.covmatic_covidseq.recipe import Recipe
from src.covmatic_covidseq.station import CovidseqBaseStation

ALL_WELLS = ["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1",
             "A2",  "B2",  "C2",  "D2",  "E2",  "F2",  "G2",  "H2",
             "A3",  "B3",  "C3",  "D3",  "E3",  "F3",  "G3",  "H3",
             "A4",  "B4",  "C4",  "D4",  "E4",  "F4",  "G4",  "H4",
             "A5",  "B5",  "C5",  "D5",  "E5",  "F5",  "G5",  "H5",
             "A6",  "B6",  "C6",  "D6",  "E6",  "F6",  "G6",  "H6",
             "A7",  "B7",  "C7",  "D7",  "E7",  "F7",  "G7",  "H7",
             "A8",  "B8",  "C8",  "D8",  "E8",  "F8",  "G8",  "H8",
             "A9",  "B9",  "C9",  "D9",  "E9",  "F9",  "G9",  "H9",
             "A10", "B10", "C10", "D10", "E10", "F10", "G10", "H10",
             "A11", "B11", "C11", "D11", "E11", "F11", "G11", "H11",
             "A12", "B12", "C12", "D12", "E12", "F12", "G12", "H12"]

mock_labware = mock.MagicMock()
mock_labware.wells.return_value = ALL_WELLS

EXPECTED_WELLS_1 = ["A1"]
EXPECTED_WELLS_2 = ["A1", "B1"]
EXPECTED_WELLS_8 = ["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1"]
EXPECTED_WELLS_96 = ALL_WELLS


class CovidseqTestStation(CovidseqBaseStation):
    def _tipracks(self):
        pass


class BaseSetup(unittest.TestCase):
    """ Base setup for test case. Please do not put tests in this class. """
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

