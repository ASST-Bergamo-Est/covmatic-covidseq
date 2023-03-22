import datetime
import json
import os.path
from datetime import datetime
from shutil import rmtree
from src.covmatic_covidseq.utils import parse_v6_log_and_create_labware_offsets_json as parse
import unittest

CURRENT_FOLDER = os.path.split(__file__)[0]


def get_path(*args):
    return os.path.join(CURRENT_FOLDER, *args)


TEST_LOGFILE = get_path('assets', 'example_otapp_v6_log.json')
EXPECTED_LABWARE_LENGTH = 10

CHECK_LABWARE_NAME = 'opentrons_96_filtertiprack_200ul'
CHECK_LABWARE_SLOT = '9'
CHECK_LABWARE_OFFSETS = {
      "x": 0.6000000000001364,
      "y": 0,
      "z": 0
}

TEMPDIR = get_path("TEMP{}".format(datetime.now().timestamp()))
TEST_OUTPUTFILE = get_path(TEMPDIR, 'test_outputfile.json')


class LogParseBaseClass(unittest.TestCase):
    def setUp(self) -> None:
        os.makedirs(TEMPDIR, exist_ok=False)


    def tearDown(self) -> None:
        print("Removing directory {}".format(TEMPDIR))
        rmtree(TEMPDIR)


class LogParseCreation(LogParseBaseClass):
    def test_file_exist(self):
        print("TEMPDIR: {}".format(TEMPDIR))
        self.assertTrue(os.path.isfile(TEST_LOGFILE))

    def test_parse(self):
        parse(TEST_LOGFILE, TEST_OUTPUTFILE)

    def test_output_file_is_created(self):
        parse(TEST_LOGFILE, TEST_OUTPUTFILE)
        self.assertTrue(os.path.isfile(TEST_OUTPUTFILE))


class TestLogCreated(LogParseBaseClass):
    def setUp(self) -> None:
        super().setUp()
        parse(TEST_LOGFILE, TEST_OUTPUTFILE)

        with open(TEST_OUTPUTFILE, "r") as f:
            self._output = json.load(f)

    def test_output_labware_length(self):
        self.assertEqual(EXPECTED_LABWARE_LENGTH, len(self._output))

    def test_output_keys(self):
        for item in self._output:
            self.assertTrue("labware_name" in item, "Checking labware name")
            self.assertTrue("offsets" in item, "Checking offsets")
            self.assertTrue("slot" in item, "Checking slot")

    def test_expected_offsets(self):
        item = list(filter(lambda x: x['labware_name'] == CHECK_LABWARE_NAME
                                and x['slot'] == CHECK_LABWARE_SLOT, self._output))[0]
        self.assertEqual(CHECK_LABWARE_OFFSETS, item['offsets'])
