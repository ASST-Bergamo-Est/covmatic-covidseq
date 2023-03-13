import json
import logging
import math
import os.path
from covmatic_robotstation.robot_station import RobotStationABC, instrument_loader, labware_loader
from abc import ABC, abstractmethod

from opentrons.protocol_api.labware import Labware

from .recipe import Recipe


class ReagentPlateException(Exception):
    pass


class ReagentPlateHelper:
    """ Class to handle the shared plate between multiple robots.
        :param labware: the labware object assigned to the plate.
        :param samples_per_row: list of n. of samples in each row. Used to calculate where to dispense reagents
        :param well_volume_limit: [ul] maximum allowable volume in a well. Used to calculate where to dispense reagents
        :param logger: optional, a logger object
    """
    def __init__(self, labware, samples_per_row, well_volume_limit: float = 100, logger=logging.getLogger(__name__)):
        if len(samples_per_row) != 8:
            raise ReagentPlateException("Samples per row passed {} values; expected 8".format(len(samples_per_row)))
        self._well_volume_limit = well_volume_limit
        self._labware = labware
        self._samples_per_row = samples_per_row
        self._assigned_columns = []
        self._reagents = {}
        self._logger = logger


    @property
    def _assigned_reagents(self):
        return [r["name"] for r in self._assigned_columns]

    @property
    def _next_free_column_index(self):
        columns = []
        for c in self._assigned_columns:
            columns += c["columns"]
        return len(columns)

    def assign_reagent(self, reagent_name: str, volume_with_overhead_per_sample: float, volume_available_per_sample: float = None):
        self._logger.info("Assigning reagent {} with volume {}".format(reagent_name, volume_with_overhead_per_sample))

        if reagent_name in self._assigned_reagents:
            raise ReagentPlateException("Reagent {} already assigned.".format(reagent_name))

        if volume_available_per_sample is None:
            volume_available_per_sample = volume_with_overhead_per_sample

        total_volumes = [s * volume_with_overhead_per_sample for s in self._samples_per_row]
        self._logger.debug("Total volumes: {}".format(total_volumes))

        wells_needed = [math.ceil(t/self._well_volume_limit) for t in total_volumes]
        num_columns = max(wells_needed)
        free_column_index = self._next_free_column_index
        columns = self._labware.columns()[free_column_index:free_column_index + num_columns]
        available_wells = [w for c in columns for w in c]

        base_volume = max(total_volumes) / max(wells_needed)
        self._logger.debug("Base volume is: {}".format(base_volume))

        rows = []
        for v in total_volumes:
            row = []
            for j in range(num_columns):
                dispensed_volume = min(base_volume, v)
                row.append(dispensed_volume)
                v = v-dispensed_volume
            rows.append(row)

        volumes = [v for r in zip(*rows) for v in r]
        self._logger.debug("Available wells: {}".format(available_wells))
        self._logger.debug("Dispensed vols: {}".format(volumes))
        wells_with_volume = [(w, v) for w, v in zip(available_wells, volumes) if v > 0]

        volume_fraction = volume_available_per_sample / volume_with_overhead_per_sample
        self._logger.info("Volume fraction is {}".format(volume_fraction))

        wells_available_volume = [(w, v*volume_fraction) for w, v in wells_with_volume]

        self._assigned_columns.append({
            "name": reagent_name,
            "columns": columns,
            "wells": wells_with_volume,
            "wells_available_volume": wells_available_volume
        })
        self._logger.info("Assigned: {}".format(self._assigned_columns[-1]))

    def get_columns_for_reagent(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            return self._assigned_columns[self._assigned_reagents.index(reagent_name)]["columns"]
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_wells_with_volume(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            return self._assigned_columns[self._assigned_reagents.index(reagent_name)]["wells"]
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_first_row_dispensed_volume(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            data = self._assigned_columns[self._assigned_reagents.index(reagent_name)]
            first_row = [c[0] for c in data["columns"]]
            return list(filter(lambda x: x[0] in first_row, data["wells"]))
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_first_row_available_volume(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            data = self._assigned_columns[self._assigned_reagents.index(reagent_name)]
            first_row = [c[0] for c in data["columns"]]
            return list(filter(lambda x: x[0] in first_row, data["wells_available_volume"]))
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))


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
                 reagent_plate_labware_name: str = "nest_96_wellplate_100ul_pcr_full_skirt",
                 reagent_plate_max_volume: float = 100,
                 wash_plate_labware_name: str = "nest_12_reservoir_15ml",
                 wash_plate_max_volume: float = 10000,
                 very_slow_vertical_speed: float = 5,
                 slow_vertical_speed: float = 10,
                 column_offset_cov2: int = 6,
                 *args, **kwargs):
        super().__init__(robot_manager_host=robot_manager_host,
                         robot_manager_port=robot_manager_port,
                         *args, **kwargs)
        self._reagent_plate_labware_name = reagent_plate_labware_name
        self._reagent_plate_max_volume = reagent_plate_max_volume
        self._wash_plate_labware_name = wash_plate_labware_name
        self._wash_plate_max_volume = wash_plate_max_volume
        self._recipes = []
        if recipe_file is not None:
            self.load_recipes_from_json(recipe_file)
        self._reagent_plate_helper = None       # Initialized afterward
        self._wash_plate_helper = None          # Initialized afterward
        self._very_slow_vertical_speed = very_slow_vertical_speed
        self._slow_vertical_speed = slow_vertical_speed
        self._column_offset_cov2 = column_offset_cov2
        self._task_name = ""

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

    def set_task_name(self, task_name: str):
        self._task_name = task_name
        self.run_stage(task_name)

    def build_stage(self, stage_name):
        return "{} {}".format(self._task_name, stage_name)

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

    def load_reagents_plate(self, slot):
        self.logger.info("Initializing Reagent plate helper on slot {}".format(slot))
        plate = self._ctx.load_labware(self._reagent_plate_labware_name, slot, "Shared reagent plate")
        self._reagent_plate_helper = ReagentPlateHelper(plate, self.num_samples_in_rows, self._reagent_plate_max_volume)
        for r in self.recipes:
            if r.use_reagent_plate:
                self._reagent_plate_helper.assign_reagent(r.name, r.volume_to_distribute, r.volume_final)
        return plate

    def load_wash_plate(self, slot):
        self.logger.info("Initializing Wash plate helper on slot {}".format(slot))
        plate = self._ctx.load_labware(self._wash_plate_labware_name, slot, "Shared wash plate")
        self._wash_plate_helper = ReagentPlateHelper(plate, self.num_samples_in_rows, self._wash_plate_max_volume)
        for r in self.recipes:
            if r.use_wash_plate:
                self._wash_plate_helper.assign_reagent(r.name, r.volume_to_distribute, r.volume_final)
        return plate

    @property
    def reagent_plate_helper(self) -> ReagentPlateHelper:
        if self._reagent_plate_helper is None:
            raise Exception("You must call load_reagents_plate before using reagent_plate_helper")
        return self._reagent_plate_helper

    @property
    def wash_plate_helper(self) -> ReagentPlateHelper:
        if self._wash_plate_helper is None:
            raise Exception("You must call load_wash_plate before using wash_plate_helper")
        return self._wash_plate_helper

    def get_columns_for_samples(self, labware, column_offset=0):
        return labware.columns()[column_offset:column_offset+self.num_cols]

    def get_samples_wells_for_labware(self, labware: Labware):
        return [w for c in self.get_columns_for_samples(labware) for w in c][:self._num_samples]

    def get_samples_COV1_for_labware(self, labware):
        return self.get_samples_wells_for_labware(labware)

    def get_samples_COV2_for_labware(self, labware):
        return [w for c in self.get_columns_for_samples(labware, self._column_offset_cov2) for w in c][:self._num_samples]

    def get_samples_first_row_for_labware(self, labware):
        return [c[0] for c in self.get_columns_for_samples(labware)]

    def get_samples_first_row_COV2_for_labware(self, labware):
        return [c[0] for c in self.get_columns_for_samples(labware, self._column_offset_cov2)]

    @abstractmethod
    def anneal_rna(self):
        pass

    @abstractmethod
    def first_strand_cdna(self):
        pass

    @abstractmethod
    def amplify_cdna(self):
        pass

    @abstractmethod
    def tagment_pcr_amplicons(self):
        pass

    @abstractmethod
    def post_tagmentation_cleanup(self):
        pass

    def body(self):
        self.set_task_name("Anneal RNA")
        self.anneal_rna()

        self.set_task_name("FS CDNA")
        self.first_strand_cdna()

        self.set_task_name("Amplify CDNA")
        self.amplify_cdna()

        self.set_task_name("TAG PCR Amplicons")
        self.tagment_pcr_amplicons()

        self.set_task_name("Post Tag Cleanup")
        self.post_tagmentation_cleanup()
