from src.covmatic_covidseq.pipette_chooser import PipetteChooser
import unittest

PIPETTE_1 = "PIPETTE1"
PIPETTE_1_VOL = 10
EXPECTED_AIR_GAP_1 = 1

PIPETTE_2 = "PIPETTE2"
PIPETTE_2_VOL = 20
EXPECTED_AIR_GAP_2 = 2

TEST_VOLS_PIPETTE_1 = [1, 2, 3, 9, 10]
TEST_VOLS_PIPETTE_2 = [11, 12, 20, 30]

TEST_VOL_PIPETTE_1_W_AIRGAP = 8
TEST_VOL_PIPETTE_2_W_AIRGAP = 9.9


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


class TestMaxVolume(TestBaseClass):
    def setUp(self) -> None:
        super().setUp()
        self._pc.register(PIPETTE_2, PIPETTE_2_VOL)
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)

    def test_get_volume_pipette_1(self):
        self.assertEqual(PIPETTE_1_VOL, self._pc.get_max_volume(PIPETTE_1))

    def test_get_volume_pipette_2(self):
        self.assertEqual(PIPETTE_2_VOL, self._pc.get_max_volume(PIPETTE_2))


class TestAirGap(TestBaseClass):
    def setUp(self) -> None:
        super().setUp()
        self._pc.register(PIPETTE_2, PIPETTE_2_VOL)
        self._pc.register(PIPETTE_1, PIPETTE_1_VOL)

    def test_get_air_gap_pipette_1(self):
        self.assertEqual(EXPECTED_AIR_GAP_1, self._pc.get_air_gap(PIPETTE_1))

    def test_get_air_gap_pipette_2(self):
        self.assertEqual(EXPECTED_AIR_GAP_2, self._pc.get_air_gap(PIPETTE_2))

    def test_pipette_1_get_with_air_gap(self):
        self.assertEqual(PIPETTE_1, self._pc.get_pipette(TEST_VOL_PIPETTE_1_W_AIRGAP, True))

    def test_pipette_2_get_with_air_gap(self):
        self.assertEqual(PIPETTE_2, self._pc.get_pipette(TEST_VOL_PIPETTE_2_W_AIRGAP, True))

    def test_pipette_1_get_max_vol_w_airgap(self):
        self.assertEqual(PIPETTE_1_VOL-EXPECTED_AIR_GAP_1, self._pc.get_max_volume(PIPETTE_1, True))

    def test_pipette_2_get_max_vol_w_airgap(self):
        self.assertEqual(PIPETTE_2_VOL-EXPECTED_AIR_GAP_2, self._pc.get_max_volume(PIPETTE_2, True))
