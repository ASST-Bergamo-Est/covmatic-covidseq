from src.covmatic_covidseq.pipette_chooser import PipetteChooser
import unittest

PIPETTE_1 = "PIPETTE1"
PIPETTE_1_VOL = 10

PIPETTE_2 = "PIPETTE2"
PIPETTE_2_VOL = 20

TEST_VOLS_PIPETTE_1 = [1, 2, 3, 9, 10]
TEST_VOLS_PIPETTE_2 = [11, 12, 20, 30]


class TestBaseClass(unittest.TestCase):
    def setUp(self) -> None:
        self._pc = PipetteChooser()


class TestPipetteRegistration(TestBaseClass):
    def test_creation(self):
        self.assertTrue(self._pc)

    def test_register_pipette_1(self):
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)
        self.assertEqual(1, len(self._pc._pipettes))

    def test_register_pipette_2(self):
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)
        self._pc.register(PIPETTE_2, PIPETTE_2_VOL)
        self.assertEqual(2, len(self._pc._pipettes))

    def test_register_pipette_order(self):
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)
        self._pc.register(PIPETTE_2, PIPETTE_2_VOL)
        self.assertEqual(PIPETTE_1, self._pc._pipettes[0]["pipette"])
        self.assertEqual(PIPETTE_2, self._pc._pipettes[1]["pipette"])

    def test_register_pipette_order_reversed(self):
        self._pc.register(PIPETTE_2, PIPETTE_2_VOL)
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)
        self.assertEqual(PIPETTE_1, self._pc._pipettes[0]["pipette"])
        self.assertEqual(PIPETTE_2, self._pc._pipettes[1]["pipette"])


class TestPipetteGet(TestBaseClass):
    def setUp(self) -> None:
        super().setUp()
        self._pc.register(PIPETTE_2, PIPETTE_2_VOL)
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)

    def test_getpipette_1(self):
        for v in TEST_VOLS_PIPETTE_1:
            self.assertEqual(PIPETTE_1, self._pc.get_pipette(v), "Testing volume {}".format(v))

    def test_getpipette_2(self):
        for v in TEST_VOLS_PIPETTE_2:
            self.assertEqual(PIPETTE_2, self._pc.get_pipette(v), "Testing volume {}".format(v))
