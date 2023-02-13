
class RecipeException(Exception):
    pass


class Recipe:
    def __init__(self,
                 name: str = "",
                 description: str = "",
                 steps=None,
                 volume_to_distribute=None):
        self._name = name
        self._description = description
        self._vol = 0
        self._steps = steps or []
        if volume_to_distribute is not None:
            self.volume_to_distribute = volume_to_distribute

    def __str__(self):
        return "Recipe name: {}; vol: {}; steps: {}".format(
            self._name,
            self._vol,
            "(" + "), (".join([", ".join([str(s[k]) for k in s.keys()]) for s in self._steps]) + ")")

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

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
        return sum([s["vol"] for s in self._steps])
