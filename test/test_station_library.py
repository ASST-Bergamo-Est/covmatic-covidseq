import unittest
from unittest import mock
from .common import logger, NUM_SAMPLES
from src.covmatic_covidseq.stations.library import LibraryStation

EXPECTED_SAMPLES_ROW_1 = ["A2"]
EXPECTED_SAMPLES_ROW_2 = ["A2"]
EXPECTED_SAMPLES_ROW_8 = ["A2"]
EXPECTED_SAMPLES_ROW_9 = ["A2", "A3"]
EXPECTED_SAMPLES_ROW_64 = ["A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
EXPECTED_SAMPLES_ROW_96 = ["A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12"]


mock_labware = mock.MagicMock()
mock_labware.columns.return_value = [["A1",  "B1",  "C1",  "D1",  "E1",  "F1",  "G1",  "H1"],
                                     ["A2",  "B2",  "C2",  "D2",  "E2",  "F2",  "G2",  "H2"],
                                     ["A3",  "B3",  "C3",  "D3",  "E3",  "F3",  "G3",  "H3"],
                                     ["A4",  "B4",  "C4",  "D4",  "E4",  "F4",  "G4",  "H4"],
                                     ["A5",  "B5",  "C5",  "D5",  "E5",  "F5",  "G5",  "H5"],
                                     ["A6",  "B6",  "C6",  "D6",  "E6",  "F6",  "G6",  "H6"],
                                     ["A7",  "B7",  "C7",  "D7",  "E7",  "F7",  "G7",  "H7"],
                                     ["A8",  "B8",  "C8",  "D8",  "E8",  "F8",  "G8",  "H8"],
                                     ["A9",  "B9",  "C9",  "D9",  "E9",  "F9",  "G9",  "H9"],
                                     ["A10", "B10", "C10", "D10", "E10", "F10", "G10", "H10"],
                                     ["A11", "B11", "C11", "D11", "E11", "F11", "G11", "H11"],
                                     ["A12", "B12", "C12", "D12", "E12", "F12", "G12", "H12"]]


class TestLibrary(unittest.TestCase):
    def setUp(self) -> None:
        self._s = LibraryStation(robot_manager_host="FAKEHOST",
                                 robot_manager_port=1234,
                                 logger=logger,
                                 num_samples=NUM_SAMPLES)

    def test_creation(self):
        self.assertTrue(self._s)

    def test_get_samples_first_row_1(self):
        self._s._num_samples = 1
        self.assertEqual(EXPECTED_SAMPLES_ROW_1, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_get_samples_first_row_2(self):
        self._s._num_samples = 2
        self.assertEqual(EXPECTED_SAMPLES_ROW_2, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_get_samples_first_row_8(self):
        self._s._num_samples = 8
        self.assertEqual(EXPECTED_SAMPLES_ROW_8, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_get_samples_first_row_9(self):
        self._s._num_samples = 9
        self.assertEqual(EXPECTED_SAMPLES_ROW_9, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_get_samples_first_row_64(self):
        self._s._num_samples = 64
        self.assertEqual(EXPECTED_SAMPLES_ROW_64, self._s.get_samples_first_row_for_labware(mock_labware))

    def test_get_samples_first_row_96(self):
        self._s._num_samples = 96
        self.assertEqual(EXPECTED_SAMPLES_ROW_96, self._s.get_samples_first_row_for_labware(mock_labware))