import unittest

from src.covmatic_covidseq.recipe import Recipe, RecipeException

EXAMPLE_STEPS_1 = [
    {
        "name": "Add reagent EPH3",
        "reagent": "EPH3",
        "vol": 10
    }]
EXPECTED_VOL_STEPS_1 = 10
VOLUME_FINAL_1 = 8
VOLUME_TO_DISTRIBUTE_1 = 10
NEEDS_EMPTY_TUBE_1 = False

RECIPE_2_NAME = "TEST RECIPE 2"
EXAMPLE_STEPS_2 = [
    {
        "name": "Add reagent EPH3",
        "reagent": "EPH3",
        "vol": 10
    },
    {
        "name": "Add water",
        "reagent": "WATER",
        "vol": 11
    }]
EXPECTED_VOL_STEPS_2 = 21
VOLUME_FINAL_2 = 19
VOLUME_TO_DISTRIBUTE_2 = 20
NEEDS_EMPTY_TUBE_2 = True


class RecipeBaseClass(unittest.TestCase):
    def setUp(self) -> None:
        self._r = Recipe()


class RecipeTest(RecipeBaseClass):
    def test_recipe_creation(self):
        self.assertTrue(self._r)

    def test_volume_not_set_raises(self):
        with self.assertRaises(RecipeException):
            v = self._r.volume_final

    def test_volume_not_enaugh_exception(self):
        with self.assertRaises(RecipeException):
            self._r.volume_final = VOLUME_FINAL_1


class RecipeSteps1(RecipeBaseClass):
    def setUp(self) -> None:
        super().setUp()
        self.setUpExpectations()

    def setUpExpectations(self):
        self._r.add_steps(EXAMPLE_STEPS_1)
        self.steps_added = EXAMPLE_STEPS_1
        self.expected_vol = EXPECTED_VOL_STEPS_1
        self.vol_final = VOLUME_FINAL_1
        self.vol_to_distribute = VOLUME_TO_DISTRIBUTE_1
        self.needs_empty_tube = NEEDS_EMPTY_TUBE_1

    def test_get_steps_are_equal(self):
        self.assertEqual(self.steps_added, self._r.steps)

    def test_total_vol(self):
        self.assertEqual(self.expected_vol, self._r.total_prepared_vol)

    def test_set_get_vol(self):
        self._r.volume_final = self.vol_final
        self.assertEqual(self.vol_final, self._r.volume_final)

    def test_get_vol_with_overhead(self):
        self._r.volume_final = self.vol_final
        self.assertEqual(self.vol_to_distribute, self._r.volume_to_distribute)

    def test_set_get_vol_not_enough(self):
        with self.assertRaises(RecipeException):
            self._r.volume_final = (self.vol_final * 2)

    def test_set_get_vol_not_enough_vol_not_set(self):
        with self.assertRaises(RecipeException):
            self._r.volume_final = (self.vol_final * 2)
        with self.assertRaises(RecipeException):
            v = self._r.volume_final

    def test_use_empty_tube(self):
        self.assertEqual(self.needs_empty_tube, self._r.needs_empty_tube)


class RecipeSteps2(RecipeSteps1):
    """ Since this class inherits from RecipeSteps1
        every test for that class will be executed also here
    """
    def setUpExpectations(self) -> None:
        self._r.add_steps(EXAMPLE_STEPS_2)
        self.steps_added = EXAMPLE_STEPS_2
        self.expected_vol = EXPECTED_VOL_STEPS_2
        self.vol_final = VOLUME_FINAL_2
        self.vol_to_distribute = VOLUME_TO_DISTRIBUTE_2
        self.needs_empty_tube = NEEDS_EMPTY_TUBE_2


class RecipeTestOverheadSingleStep(RecipeBaseClass):
    def setUp(self) -> None:
        super().setUp()
        self._r.add_steps(EXAMPLE_STEPS_1)
        self._r.volume_final = VOLUME_FINAL_1

    def test_single_step_no_overhead(self):
        self.assertEqual(VOLUME_TO_DISTRIBUTE_1, self._r.volume_to_distribute)

HEADROOM_DEFAULT = 0.5
HEADROOM_FRACTION_1 = 0.1
REAGENT_2_VOLUME_TO_DISTRIBUTE_FRACTION_1 = 20.8

HEADROOM_FRACTION_2 = 0.7
REAGENT_2_VOLUME_TO_DISTRIBUTE_FRACTION_2 = 19.6


class RecipeTestOverhead(RecipeBaseClass):
    def setUp(self) -> None:
        super().setUp()
        self._r.add_steps(EXAMPLE_STEPS_2)
        self._r.volume_final = VOLUME_FINAL_2

    def test_default_headroom(self):
        self.assertEqual(HEADROOM_DEFAULT, self._r.headroom_fraction)

    def test_fraction_1(self):
        self._r.headroom_fraction = HEADROOM_FRACTION_1
        self.assertEqual(REAGENT_2_VOLUME_TO_DISTRIBUTE_FRACTION_1, self._r.volume_to_distribute)

    def test_fraction_2(self):
        self._r.headroom_fraction = HEADROOM_FRACTION_2
        self.assertEqual(REAGENT_2_VOLUME_TO_DISTRIBUTE_FRACTION_2, self._r.volume_to_distribute)

    def test_fraction_limit_up(self):
        with self.assertRaises(RecipeException):
            self._r.headroom_fraction = 1.1

    def test_fraction_limit_down(self):
        with self.assertRaises(RecipeException):
            self._r.headroom_fraction = -0.1



class TestRecipeWashPlate(unittest.TestCase):
    def test_nothing_specified(self):
        r = Recipe()
        self.assertFalse(r.use_wash_plate)

    def test_washplate_sets(self):
        r = Recipe(use_wash_plate=True)
        self.assertTrue(r.use_wash_plate)

    def test_washplate_unsets_reagent(self):
        r = Recipe(use_wash_plate=True)
        self.assertFalse(r.use_reagent_plate)
