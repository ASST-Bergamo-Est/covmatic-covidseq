
class RecipeException(Exception):
    pass


class Recipe:
    def __init__(self,
                 name: str = "",
                 description: str = "",
                 steps=None,
                 volume_final=None):
        self._name = name
        self._description = description
        self._vol = 0
        self._steps = steps or []
        if volume_final is not None:
            self.volume_final = volume_final

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
        """ The volume to distrubute for the first transfer from primary tube. Includes overhead."""
        if self._vol > 0:
            return (self._vol + self.total_prepared_vol) / 2
        raise RecipeException("Total volume not set")

    @property
    def volume_final(self):
        """ The volume to use for the final transfer to samples plate. Do not include overheads."""
        if self._vol > 0:
            return self._vol
        raise RecipeException("Total volume not set")

    @volume_final.setter
    def volume_final(self, v):
        """ The volume to use for the final transfer to samples plate. Do not include overheads."""
        if v <= self.total_prepared_vol:
            self._vol = v
        else:
            raise RecipeException("Requested volume not enough in recipe")

    @property
    def total_prepared_vol(self):
        """ Returns the sum of volume for each reagent in the recipe """
        return sum([s["vol"] for s in self._steps])
