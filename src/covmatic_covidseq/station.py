import json
import math
import os.path

from covmatic_robotstation.robot_station import RobotStationABC, instrument_loader, labware_loader
from abc import ABC

from .recipe import Recipe


class ReagentPlateException(Exception):
    pass

class ReagentPlate:
    """ Class to handle the shared plate between multiple robots.
        @param labware_definition: the name of the labware to load
    """
    def __init__(self, labware, samples_per_row, well_volume_limit=100):
        if len(samples_per_row) != 8:
            raise ReagentPlateException("Samples per row passed {} values; expected 8".format(len(samples_per_row)))
        self._well_volume_limit = well_volume_limit
        self._labware = labware
        self._samples_per_row = samples_per_row
        self._assigned_columns = []
        self._reagents = {}


    @property
    def _assigned_reagents(self):
        return [r["name"] for r in self._assigned_columns]

    @property
    def _next_free_column_index(self):
        columns = []
        for c in self._assigned_columns:
            columns += c["columns"]
            print("Columns are: {}".format(columns))

        return len(columns)

    def assign_reagent(self, reagent_name: str, reagent_volume_per_sample: float):
        if reagent_name in self._assigned_reagents:
            raise ReagentPlateException("Reagent {} already assigned.".format(reagent_name))
        print("Reagent {}: calculating volume for {}ul per sample".format(reagent_name, reagent_volume_per_sample))
        total_volumes = [s * reagent_volume_per_sample for s in self._samples_per_row]
        print("Total volumes: {}".format(total_volumes))
        wells_needed = [math.ceil(t/self._well_volume_limit) for t in total_volumes]
        # volumes_per_well =
        print("Calculating number of wells needed: {}".format(wells_needed))
        num_columns = max(wells_needed)
        print("Columns used: {}".format(num_columns))
        volume_per_wells = [t/w for t, w in zip(total_volumes, wells_needed)]
        print("Volume per wells = {}".format(volume_per_wells))
        free_column_index = self._next_free_column_index
        columns = self._labware.columns()[free_column_index:free_column_index+num_columns]
        wells = [w for c in columns for w in c]
        print("Wells = {}".format(wells))
        self._assigned_columns.append({
            "name": reagent_name,
            "columns": columns,
            "wells": [(w, volume_per_wells[0]) for w in wells]
        })
        print("Appended: {}".format(self._assigned_columns[-1]))

    def get_columns_for_reagent(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            return self._assigned_columns[self._assigned_reagents.index(reagent_name)]["columns"]
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_wells_with_volume(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            return self._assigned_columns[self._assigned_reagents.index(reagent_name)]["wells"]

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
