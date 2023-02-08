
class RecipeException(Exception):
    pass


class Recipe:
    def __init__(self, steps=None):
        self._steps = steps or []
        self._vol = 0

    def add_steps(self, steps):
        self._steps += steps

    @property
    def steps(self):
        return self._steps

    @property
    def volume_to_distribute(self):
        if self._vol > 0:
            return self._vol
        raise RecipeException("Total volume not set")

    @volume_to_distribute.setter
    def volume_to_distribute(self, v):
        """ Sets the final volume of the recipe mix to be dispensed."""
        if v <= self.total_prepared_vol:
            self._vol = v
        else:
            raise RecipeException("Requested volume not enough in recipe")

    @property
    def total_prepared_vol(self):
        """ Returns the sum of volume for each reagent in the recipe """
        for s in self._steps:
            print("Step: {}".format(s))
        return sum([s["vol"] for s in self._steps])
