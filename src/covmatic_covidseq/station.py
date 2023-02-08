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
                 *args, **kwargs):
        super().__init__(robot_manager_host=robot_manager_host,
                         robot_manager_port=robot_manager_port,
                         *args, **kwargs)

        self._recipes = []

    def add_recipe(self, name, recipe: Recipe):
        recipe = {
            "name": name,
            "recipe": recipe
        }
        self._recipes.append(recipe)

    def get_recipe(self, name):
        recipes_name = [r["name"] for r in self._recipes]
        try:
            index = recipes_name.index(name)
            return self._recipes[index]["recipe"]
        except ValueError as e:
            self.logger.error("GetRecipe Value error for name {}: {}".format(name, e))
            return None

