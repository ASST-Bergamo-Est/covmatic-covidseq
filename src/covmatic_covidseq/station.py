import json
import math
import os.path

from covmatic_robotstation.robot_station import RobotStationABC, instrument_loader, labware_loader
from abc import ABC

from .recipe import Recipe


class CovidseqBaseStation(RobotStationABC, ABC):
    """ Base class that has shared information about Covidseq protocol.
        Covidseq is executed by two robot:
        - REAGENT OT: prepares solutions from reagents
        - LIBRARY OT: dispenses solutions prepared to the samples.
        Between these two robot we've a reagent plate going back and forth,
        so a common class that assigns everything shared is helpful.

        Note: this is an abstract class because each OT will have its own implementation.
    """
    def __init__(self,
                 robot_manager_host: str,
                 robot_manager_port: int,
                 recipe_file: str or None = "recipes.json",
                 *args, **kwargs):
        super().__init__(robot_manager_host=robot_manager_host,
                         robot_manager_port=robot_manager_port,
                         *args, **kwargs)
        self._recipes = []
        if recipe_file is not None:
            self.load_recipes_from_json(recipe_file)

    def add_recipe(self, recipe: Recipe):
        self._recipes.append(recipe)

    def get_recipe(self, name) -> Recipe:
        recipes_name = [r.name for r in self._recipes]
        try:
            index = recipes_name.index(name)
            return self._recipes[index]
        except ValueError as e:
            self.logger.error("GetRecipe Value error for name {}: {}".format(name, e))
            return None

    @property
    def recipes(self) -> [Recipe]:
        return self._recipes

    def load_recipes_from_json(self, file):
        if not os.path.isabs(file):
            current_folder = os.path.split(__file__)[0]
            abspath = os.path.join(current_folder, file)
        else:
            abspath = file
        self.logger.info("Loading recipes from {}".format(abspath))

        with open(abspath, "r") as f:
            data = json.load(f)
            for d in data:
                self.add_recipe(Recipe(**d))
