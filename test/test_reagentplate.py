import unittest
from itertools import repeat
from unittest.mock import MagicMock

from src.covmatic_covidseq.station import ReagentPlate, ReagentPlateException

COLUMN_1 = ["A1", "B1", "C1", "D1", "E1", "F1", "G1"]
COLUMN_2 = ["A2", "B2", "C2", "D2", "E2", "F2", "G2"]

labware_mock = MagicMock()
labware_mock.columns.return_value = [COLUMN_1, COLUMN_2]

REAGENT1_NAME = "EPH3"
REAGENT1_VOLUME = 10
REAGENT1_EXPECTED_USED_COLUMNS = [COLUMN_1]
REAGENT1_EXPECTED_VOLUME_FOR_WELL = 10

REAGENT2_NAME = "EPH4"
REAGENT2_VOLUME = 120
REAGENT2_EXPECTED_USED_COLUMNS = [COLUMN_1, COLUMN_2]
REAGENT2_EXPECTED_VOLUME_FOR_WELL = 60

SAMPLES_PER_ROW = [1, 1, 1, 1, 1, 1, 1, 1]


SAMPLES_PER_ROW_LESS = [1, 2, 3, 4, 5, 6, 7]
SAMPLES_PER_ROW_MORE = [1, 2, 3, 4, 5, 6, 7, 8, 9]

class BaseTestClass(unittest.TestCase):
    def setUp(self):
        self._rp = ReagentPlate(labware_mock, SAMPLES_PER_ROW)


class TestReagentPlate(BaseTestClass):
    def test_creation(self):
        self.assertTrue(self._rp)

    def test_assign_reagent(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)

    def test_reagent_already_assigned(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        with self.assertRaises(ReagentPlateException):
            self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)

    def test_reagent_not_found(self):
        with self.assertRaises(ReagentPlateException):
            self._rp.get_columns_for_reagent(REAGENT1_NAME)

    def test_free_columns_start_from_zero(self):
        self.assertEqual(0, self._rp._next_free_column_index)


class TestReagent1(BaseTestClass):
    def setUp(self):
        super().setUp()
        self.setUpExpectations()

    def setUpExpectations(self):
        self._reagent_name = REAGENT1_NAME
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        self._expected_used_columns = REAGENT1_EXPECTED_USED_COLUMNS
        self._expected_wells_volume = list(repeat(REAGENT1_EXPECTED_VOLUME_FOR_WELL, sum([len(c) for c in self._expected_used_columns])))

    def test_free_columns(self):
        self.assertEqual(len(self._expected_used_columns), self._rp._next_free_column_index)

    def test_get_columns_for_reagent(self):
        self.assertEqual(self._expected_used_columns, self._rp.get_columns_for_reagent(self._reagent_name))

    def test_get_wells_with_volume(self):
        for i, (w, v) in enumerate(self._rp.get_wells_with_volume(self._reagent_name)):
            self.assertEqual(self._expected_wells_volume[i], v, "Checking well {}".format(w))


class TestReagent2(TestReagent1):
    def setUpExpectations(self):
        self._reagent_name = REAGENT2_NAME
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        self._expected_used_columns = REAGENT2_EXPECTED_USED_COLUMNS
        self._expected_wells_volume = list(repeat(REAGENT2_EXPECTED_VOLUME_FOR_WELL, sum([len(c) for c in self._expected_used_columns])))


class TestInitializationArguments(unittest.TestCase):
    def test_wrong_samples_per_row_less(self):
        with self.assertRaises(ReagentPlateException):
            ReagentPlate(labware_mock, SAMPLES_PER_ROW_LESS)

    def test_wrong_samples_per_row_more(self):
        with self.assertRaises(ReagentPlateException):
            ReagentPlate(labware_mock, SAMPLES_PER_ROW_MORE)
