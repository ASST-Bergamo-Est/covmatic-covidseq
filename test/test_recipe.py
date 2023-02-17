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
VOLUME_TO_DISTRIBUTE_1 = 9

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
