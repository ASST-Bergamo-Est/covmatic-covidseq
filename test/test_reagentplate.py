import unittest
from .common import logger
from unittest.mock import MagicMock

from src.covmatic_covidseq.station import ReagentPlate, ReagentPlateException

COLUMN_1 = ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1"]
COLUMN_2 = ["A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2"]
COLUMN_3 = ["A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3"]
COLUMN_4 = ["A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4"]

labware_mock = MagicMock()
labware_mock.columns.return_value = [COLUMN_1, COLUMN_2, COLUMN_3, COLUMN_4]

SAMPLES_PER_ROW = [1, 1, 1, 1, 1, 1, 1, 1]
SAMPLES_PER_ROW_LESS = [1, 2, 3, 4, 5, 6, 7]
SAMPLES_PER_ROW_MORE = [1, 2, 3, 4, 5, 6, 7, 8, 9]


REAGENT1_NAME = "EPH3"
REAGENT1_VOLUME = 10
REAGENT1_EXPECTED_USED_COLUMNS = [COLUMN_1]
REAGENT1_EXPECTED_VOLUME_FOR_WELL = [10, 10, 10, 10, 10, 10, 10, 10]

REAGENT2_NAME = "EPH4"
REAGENT2_VOLUME = 120
REAGENT2_EXPECTED_USED_COLUMNS = [COLUMN_1, COLUMN_2]
REAGENT2_EXPECTED_VOLUME_FOR_WELL = [100, 100, 100, 100, 100, 100, 100, 100,
                                     20,  20,  20,  20,  20,  20,  20,  20]

# Assigning both reagent 1 and 2
REAGENT12_EXPECTED_USED_COLUMNS_FOR_REAGENT2 = [COLUMN_2, COLUMN_3]

# Simulating a number of samples not multiple by 8
NOT_8_MULTIPLE_SAMPLES_PER_ROW = [2, 2, 2, 1, 1, 1, 1, 1]
NOT_8_MULTIPLE_REAGENT1_EXPECTED_USED_COLUMNS = [COLUMN_1]
NOT_8_MULTIPLE_REAGENT1_EXPECTED_VOLUMES_FOR_WELL = [20, 20, 20, 10, 10, 10, 10, 10]

NOT_8_MULTIPLE_REAGENT2_EXPECTED_USED_COLUMNS = [COLUMN_1]
NOT_8_MULTIPLE_REAGENT2_EXPECTED_VOLUMES_FOR_WELL = [100, 100, 100, 100, 100, 100, 100, 100,
                                                     100, 100, 100, 20,  20,  20,  20,  20,
                                                     40, 40, 40]


class BaseTestClass(unittest.TestCase):
    def setUp(self):
        self._rp = ReagentPlate(labware_mock, SAMPLES_PER_ROW, logger=logger)


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
        self._expected_wells_volume = REAGENT1_EXPECTED_VOLUME_FOR_WELL

    def test_get_columns_for_reagent(self):
        self.assertEqual(self._expected_used_columns, self._rp.get_columns_for_reagent(self._reagent_name))

    def test_get_wells_with_volume(self):
        for i, (w, v) in enumerate(self._rp.get_wells_with_volume(self._reagent_name)):
            self.assertEqual(self._expected_wells_volume[i], v, "Checking well {}".format(w))

    def test_wells_not_empty(self):
        self.assertGreater(len(self._rp.get_wells_with_volume(self._reagent_name)), 0)


class TestReagent2(TestReagent1):
    def setUpExpectations(self):
        self._reagent_name = REAGENT2_NAME
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        self._expected_used_columns = REAGENT2_EXPECTED_USED_COLUMNS
        self._expected_wells_volume = REAGENT2_EXPECTED_VOLUME_FOR_WELL


class TestReagent12(TestReagent1):
    def setUpExpectations(self):
        self._reagent_name = REAGENT2_NAME
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        self._expected_used_columns = REAGENT12_EXPECTED_USED_COLUMNS_FOR_REAGENT2
        self._expected_wells_volume = REAGENT2_EXPECTED_VOLUME_FOR_WELL


class TestFreeColumns(BaseTestClass):
    def test_used_0_columns(self):
        self.assertEqual(0, self._rp._next_free_column_index)

    def test_used_1_columns(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        self.assertEqual(len(REAGENT1_EXPECTED_USED_COLUMNS), self._rp._next_free_column_index)

    def test_used_2_columns(self):
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        self.assertEqual(len(REAGENT2_EXPECTED_USED_COLUMNS), self._rp._next_free_column_index)

    def test_used_3_columns(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        self.assertEqual(len(REAGENT1_EXPECTED_USED_COLUMNS + REAGENT2_EXPECTED_USED_COLUMNS), self._rp._next_free_column_index)


class TestNotMultipleBy8(unittest.TestCase):
    def setUp(self):
        self._rp = ReagentPlate(labware_mock, NOT_8_MULTIPLE_SAMPLES_PER_ROW, logger=logger)

    def test_reagent_1_columns(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        self.assertEqual(NOT_8_MULTIPLE_REAGENT1_EXPECTED_USED_COLUMNS, self._rp.get_columns_for_reagent(REAGENT1_NAME))

    def test_reagent_1_wells(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        self.assertGreater(len(self._rp.get_wells_with_volume(REAGENT1_NAME)), 0)

    def test_reagent_1_volumes(self):
        self._rp.assign_reagent(REAGENT1_NAME, REAGENT1_VOLUME)
        wells_with_volumes = self._rp.get_wells_with_volume(REAGENT1_NAME)
        for expected, calculated in zip(NOT_8_MULTIPLE_REAGENT1_EXPECTED_VOLUMES_FOR_WELL, [v for (_, v) in wells_with_volumes]):
            self.assertEqual(expected, calculated)

    def test_reagent_2_wells(self):
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        self.assertGreater(len(self._rp.get_wells_with_volume(REAGENT2_NAME)), 0)

    def test_reagent_2_volumes(self):
        self._rp.assign_reagent(REAGENT2_NAME, REAGENT2_VOLUME)
        wells_with_volumes = self._rp.get_wells_with_volume(REAGENT2_NAME)
        for expected, calculated in zip(NOT_8_MULTIPLE_REAGENT2_EXPECTED_VOLUMES_FOR_WELL, [v for (_, v) in wells_with_volumes]):
            self.assertEqual(expected, calculated)


class TestInitializationArguments(unittest.TestCase):
    def test_wrong_samples_per_row_less(self):
        with self.assertRaises(ReagentPlateException):
            ReagentPlate(labware_mock, SAMPLES_PER_ROW_LESS, logger=logger)

    def test_wrong_samples_per_row_more(self):
        with self.assertRaises(ReagentPlateException):
            ReagentPlate(labware_mock, SAMPLES_PER_ROW_MORE, logger=logger)
