
class RecipeException(Exception):
    pass


class Recipe:
    def __init__(self,
                 name: str = "",
                 description: str = "",
                 steps=None,
                 volume_final=None,
                 use_reagent_plate=True,
                 headroom_fraction=0.5):
        self._name = name
        self._description = description
        self._vol = 0
        self._steps = steps or []
        if volume_final is not None:
            self.volume_final = volume_final
        self._use_reagent_plate = use_reagent_plate
        self._headroom_fraction = headroom_fraction

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
    def use_reagent_plate(self):
        return self._use_reagent_plate

    @property
    def headroom_fraction(self):
        return self._headroom_fraction

    @headroom_fraction.setter
    def headroom_fraction(self, f):
        """ Fraction of headroom volume to be left in the first transfer.
            The remaining if available for the second transfer
            eg.  vol prepared ----------------- vol final
                                |
                               0.1  means that 10% of headroom remains in first tube, 90% is transferred to plate
        """
        if 0 <= f <= 1:
            self._headroom_fraction = f
        else:
            raise RecipeException("Headroom fraction must be greater or equal than 0 and minor or equal 1")

    @property
    def volume_to_distribute(self):
        """ The volume to distrubute for the first transfer from primary tube. Includes overhead."""
        if self._vol > 0:
            return (1-self._headroom_fraction) * self.total_prepared_vol + self._headroom_fraction * self._vol
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
