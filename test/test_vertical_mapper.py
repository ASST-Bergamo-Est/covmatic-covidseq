import unittest
from .common import logger
from src.covmatic_covidseq.vertical_mapper import VerticalMapper

LABWARE_COLUMNS = [["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11", "H12"],
                   ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"],
                   ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
                   ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12"],
                   ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12"],
                   ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12"],
                   ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "B12"],
                   ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12"]]

# Value for automatic choose of start well
EXPECTED_MAP_1 = ['E3']
EXPECTED_MAP_8 = ['E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10']
EXPECTED_MAP_9 = ['E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10', 'D3']
EXPECTED_MAP_16 = ['E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                   'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10']

EXPECTED_MAP_17 = ['F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10',
                   'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                   'D3']

EXPECTED_MAP_24 = ['F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10',
                   'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                   'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10']

EXPECTED_MAP_25 = ['F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10',
                   'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                   'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10',
                   'C3']

EXPECTED_MAP_32 = ['F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10',
                   'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                   'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10',
                   'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10']

EXPECTED_MAP_33 = ['G3', 'G4', 'G5', 'G6', 'G7', 'G8', 'G9', 'G10',
                   'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10',
                   'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                   'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10',
                   'C3']

# ['E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
#  'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10',
#  'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10',
#  'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10',
#  'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10']
class TestVerticalMapper(unittest.TestCase):
    def setUp(self) -> None:
        self._vm = VerticalMapper(LABWARE_COLUMNS, logger)

    def test_map_for_samples_1(self):
        self.assertEqual(EXPECTED_MAP_1, self._vm.get_map_for_samples(1))

    def test_map_for_samples_8(self):
        self.assertEqual(EXPECTED_MAP_8, self._vm.get_map_for_samples(8))

    def test_map_for_samples_9(self):
        self.assertEqual(EXPECTED_MAP_9, self._vm.get_map_for_samples(9))

    def test_map_for_samples_16(self):
        self.assertEqual(EXPECTED_MAP_16, self._vm.get_map_for_samples(16))

    def test_map_for_samples_17(self):
        self.assertEqual(EXPECTED_MAP_17, self._vm.get_map_for_samples(17))

    def test_map_for_samples_24(self):
        self.assertEqual(EXPECTED_MAP_24, self._vm.get_map_for_samples(24))

    def test_map_for_samples_25(self):
        self.assertEqual(EXPECTED_MAP_25, self._vm.get_map_for_samples(25))

    def test_map_for_samples_32(self):
        self.assertEqual(EXPECTED_MAP_32, self._vm.get_map_for_samples(32))

    def test_map_for_samples_33(self):
        self.assertEqual(EXPECTED_MAP_33, self._vm.get_map_for_samples(33))