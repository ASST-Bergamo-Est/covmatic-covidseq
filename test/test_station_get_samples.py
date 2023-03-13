import logging
import unittest
from unittest import mock

from .common import CovidseqTestStation

ALL_COLUMNS = [["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1"],
               ["A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2"],
               ["A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3"],
               ["A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4"],
               ["A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5"],
               ["A6", "B6", "C6", "D6", "E6", "F6", "G6", "H6"],
               ["A7", "B7", "C7", "D7", "E7", "F7", "G7", "H7"],
               ["A8", "B8", "C8", "D8", "E8", "F8", "G8", "H8"],
               ["A9", "B9", "C9", "D9", "E9", "F9", "G9", "H9"],
               ["A10", "B10", "C10", "D10", "E10", "F10", "G10", "H10"],
               ["A11", "B11", "C11", "D11", "E11", "F11", "G11", "H11"],
               ["A12", "B12", "C12", "D12", "E12", "F12", "G12", "H12"]]

ALL_WELLS = [w for c in ALL_COLUMNS for w in c]

mock_labware = mock.MagicMock()
mock_labware.wells.return_value = ALL_WELLS
mock_labware.columns.return_value = ALL_COLUMNS

EXPECTED_WELLS_1 = ["A1"]
EXPECTED_WELLS_2 = ["A1", "B1"]
EXPECTED_WELLS_8 = ["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1"]
EXPECTED_WELLS_96 = ALL_WELLS

EXPECTED_WELLS_1_OFFSET_48 = ["A7"]
EXPECTED_WELLS_2_OFFSET_48 = ["A7", "B7"]
EXPECTED_WELLS_8_OFFSET_48 = ["A7",  "B7",  "C7",  "D7",  "E7",  "F7",  "G7",  "H7"]
EXPECTED_WELLS_9_OFFSET_48 = ["A7",  "B7",  "C7",  "D7",  "E7",  "F7",  "G7",  "H7",  "A8"]

EXPECTED_COLUMNS_1 = [["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1"]]
EXPECTED_COLUMNS_8 = [["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1"]]
EXPECTED_COLUMNS_9 = [["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1"], 
                      ["A2",  "B2",  "C2",  "D2",  "E2",  "F2",  "G2",  "H2"]]

EXPECTED_FIRST_ROW_1 = ["A1"]
EXPECTED_FIRST_ROW_8 = ["A1"]
EXPECTED_FIRST_ROW_9 = ["A1", "A2"]

EXPECTED_FIRST_ROW_1_COV2 = ["A7"]
EXPECTED_FIRST_ROW_8_COV2 = ["A7"]
EXPECTED_FIRST_ROW_9_COV2 = ["A7", "A8"]


class BaseSetup(unittest.TestCase):
    """ Base setup for test case. Please do not put tests in this class. """
    def setUp(self):
        self._s = CovidseqTestStation(robot_manager_host="FAKEHOST",
                                      robot_manager_port=1234,
                                      ot_name="TEST",
                                      recipe_file=None,
                                      logger=logging.getLogger())


class TestGetSamples(BaseSetup):
    def test_get_samples_1(self):
        self._s._num_samples = 1
        self.assertEqual(EXPECTED_WELLS_1, self._s.get_samples_wells_for_labware(mock_labware))

    def test_get_samples_2(self):
        self._s._num_samples = 2
        self.assertEqual(EXPECTED_WELLS_2, self._s.get_samples_wells_for_labware(mock_labware))

    def test_get_samples_8(self):
        self._s._num_samples = 8
        self.assertEqual(EXPECTED_WELLS_8, self._s.get_samples_wells_for_labware(mock_labware))

    def test_get_samples_96(self):
        self._s._num_samples = 96
        self.assertEqual(EXPECTED_WELLS_96, self._s.get_samples_wells_for_labware(mock_labware))


class TestGetSamplesCov2(BaseSetup):
    def test_get_samples_1(self):
        self._s._num_samples = 1
        self.assertEqual(EXPECTED_WELLS_1_OFFSET_48, self._s.get_samples_COV2_for_labware(mock_labware))

    def test_get_samples_2(self):
        self._s._num_samples = 2
        self.assertEqual(EXPECTED_WELLS_2_OFFSET_48, self._s.get_samples_COV2_for_labware(mock_labware))

    def test_get_samples_8(self):
        self._s._num_samples = 8
        self.assertEqual(EXPECTED_WELLS_8_OFFSET_48, self._s.get_samples_COV2_for_labware(mock_labware))

    def test_get_samples_9(self):
        self._s._num_samples = 9
        self.assertEqual(EXPECTED_WELLS_9_OFFSET_48, self._s.get_samples_COV2_for_labware(mock_labware))


class TestGetColumns(BaseSetup):
    def test_columns_1_sample(self):
        self._s._num_samples = 1
        self.assertEqual(EXPECTED_COLUMNS_1, self._s.get_columns_for_samples(mock_labware))

    def test_columns_8_sample(self):
        self._s._num_samples = 8
        self.assertEqual(EXPECTED_COLUMNS_8, self._s.get_columns_for_samples(mock_labware))

    def test_columns_9_sample(self):
        self._s._num_samples = 9
        self.assertEqual(EXPECTED_COLUMNS_9, self._s.get_columns_for_samples(mock_labware))


class TestGetSamplesFirstRow(BaseSetup):
    def test_1_sample(self):
        self._s._num_samples = 1
        self.assertEqual(EXPECTED_FIRST_ROW_1, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_8_sample(self):
        self._s._num_samples = 8
        self.assertEqual(EXPECTED_FIRST_ROW_8, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_9_sample(self):
        self._s._num_samples = 9
        self.assertEqual(EXPECTED_FIRST_ROW_9, self._s.get_samples_first_row_for_labware(mock_labware))


class TestGetSamplesFirstRowCov2(BaseSetup):
    def test_1_sample(self):
        self._s._num_samples = 1
        self.assertEqual(EXPECTED_FIRST_ROW_1_COV2, self._s.get_samples_first_row_COV2_for_labware(mock_labware))

    def test_8_sample(self):
        self._s._num_samples = 8
        self.assertEqual(EXPECTED_FIRST_ROW_8_COV2, self._s.get_samples_first_row_COV2_for_labware(mock_labware))

    def test_9_sample(self):
        self._s._num_samples = 9
        self.assertEqual(EXPECTED_FIRST_ROW_9_COV2, self._s.get_samples_first_row_COV2_for_labware(mock_labware))

