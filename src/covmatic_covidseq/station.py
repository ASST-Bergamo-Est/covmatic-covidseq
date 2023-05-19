import inspect
import json
import logging
import os.path
from typing import Optional

from covmatic_robotstation.robot_station import RobotStationABC, instrument_loader, labware_loader
from abc import ABC, abstractmethod

from opentrons import types
from opentrons.protocol_api.labware import Labware

from .reagent_helper import ReagentPlateHelper, ReagentPlateException
from .recipe import Recipe





class ConfigFileException(Exception):
    pass


class ConfigFile:
    def __init__(self, filepath, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._logger.info("Loading config file from {}".format(filepath))
        try:
            with open(filepath, "r") as f:
                config = json.load(f)
                for key in config:
                    self._logger.debug("Config set attribute {}: {}".format(key, config[key]))
                    setattr(self, key, config[key])
        except FileNotFoundError:
            self._logger.warning("Config file not found: {}".format(filepath))

    def __getattr__(self, name: str):
        if f"{name}" not in self.__dict__:
            raise ConfigFileException("Config key {} not found".format(name))
        return self.__dict__[f"{name}"]


class FlowRatesException(Exception):
    pass


class FlowRates:
    def __init__(self, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._logger.info("Initializing FlowRates class")
        self._flow_rates = None

    def load_from_file(self, filepath):
        self._logger.info("Opening flow rates from json: {}".format(filepath))
        with open(filepath, "r") as f:
            self._flow_rates = json.load(f)
        self._logger.info("Loaded flow rates: {}".format(self._flow_rates))

    def get(self, flow_rate_name):
        if self._flow_rates is None:
            self._logger.warning("Requested flow rate {} but no flow rates loaded.".format(flow_rate_name))
            return self.default_flow_rate

        if flow_rate_name not in self._flow_rates:
            raise FlowRatesException("Flow rate {} not found.".format(flow_rate_name))

        return self._flow_rates[flow_rate_name]

    def get_defaults(self, pipette_name):
        return self.get("defaults-{}".format(pipette_name))

    @property
    def default_flow_rate(self):
        return {"aspirate": None, "dispense": None, "blow_out": None}


class CovidseqBaseStation(RobotStationABC, ABC):
    def __init__(self,
                 robot_manager_host: str = None,
                 robot_manager_port: int = None,
                 recipe_file: str or None = "recipes.json",
                 reagent_plate_labware_name: str = "nest_96_wellplate_100ul_pcr_full_skirt",
                 reagent_plate_max_volume: float = 100,
                 wash_plate_labware_name: str = "nest_12_reservoir_15ml",
                 wash_plate_max_volume: float = 10000,
                 very_slow_vertical_speed: float = 5,
                 slow_vertical_speed: float = 10,
                 column_offset_cov2: int = 6,
                 pcr_mastermix_with_index_col_offset=6,
                 flow_rate_json_filepath=None,
                 offsets_json_filepath="/var/lib/jupyter/notebooks/config/labware_offsets.json",
                 config_json_filepath="/var/lib/jupyter/notebooks/config/config.json",
                 labware_load_offset: bool = False,
                 drop_loc_l: float = -10,
                 drop_loc_r: float = 20,
                 drop_height: float = -10,
                 *args, **kwargs):
        """ Base class that has shared information about Covidseq protocol.
            **Note**: you must stop opentrons-robot-server service before starting this protocol to avoid
                      problems with modules.
            
            Covidseq is executed by two robot:
            - REAGENT OT: prepares solutions from reagents
            - LIBRARY OT: dispenses solutions prepared to the samples.
            Between these two robot we've a reagent plate going back and forth,
            so a common class that assigns everything shared is helpful.
            **Note**: this is an abstract class because each OT will have its own implementation.

            :param labware_load_offset: if True loads labware offset from specified file. Do not use with OT App.
            :param drop_loc_l: offset for dropping to the left side (should be positive) in mm
            :param drop_loc_r: offset for dropping to the right side (should be negative) in mm
            :param drop_height: the height at which the drop tip occurs
        """
        self._config = ConfigFile(config_json_filepath)
        super().__init__(robot_manager_host=robot_manager_host or self._config.robot_manager_host,
                         robot_manager_port=robot_manager_port or self._config.robot_manager_port,
                         drop_loc_l=drop_loc_l, drop_loc_r=drop_loc_r, drop_height=drop_height,
                         dummy_lights=False,
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
        self._pcr_mastermix_with_index_col_offset = pcr_mastermix_with_index_col_offset
        self._offsets_json_filepath = offsets_json_filepath
        self._labware_load_offset = labware_load_offset
        self._task_name = ""
        self._offsets = []
        self._current_flow_rate = {'aspirate': None, 'dispense': None, 'blow_out': None}
        self._flow_rates = FlowRates()
        if flow_rate_json_filepath is not None:
            self._flow_rates.load_from_file(self.check_and_get_absolute_path(flow_rate_json_filepath))

    def pre_loaders_initializations(self):
        super().pre_loaders_initializations()
        self.load_offsets()
        self._load_reagent_plate()
        self._ctx.set_rail_lights(True)

    def load_offsets(self):
        """ Warning: offset must be loaded only for opentrons_execute.
            Do not use set_offset with Opentrons App Labware Check
        """
        if self._labware_load_offset:
            self._offsets = self._load_offsets_from_file(self._offsets_json_filepath)
            self.logger.info("Loaded offsets: {}".format(self._offsets))

    def _load_offsets_from_file(self, filepath):
        self.logger.info("Loading offsets from {}".format(filepath))
        try:
            with open(filepath, "r") as f:
                offsets = json.load(f)
        except FileNotFoundError:
            if self._ctx.is_simulating():
                offsets = []
                self.logger.warning("Labware offset file not found: {}".format(filepath))
            else:
                raise Exception("Labware offset file not found: {}. Please create it before starting the run"
                                .format(filepath))
        return offsets

    def apply_offset_to_labware(self, labware: Labware):
        self.logger.info("Searching offset for labware: {}".format(labware.load_name))
        if self._labware_load_offset:
            for slot in self._ctx.loaded_labwares:
                if self._ctx.loaded_labwares[slot] == labware:
                    labware_slot = slot
                    self.logger.info("Found slot {} for labware {}".format(labware_slot, labware.load_name))
                    break
            else:
                raise Exception("Offset for labware: slot not found for labware {}".format(labware.load_name))

            offset = list(filter(
                    lambda x: (x['slot'] == str(labware_slot) and x['labware_name'] == labware.load_name), self._offsets))

            if len(offset) == 1:
                self.logger.info("Labware {} applying offset {}".format(
                    labware.load_name,
                    ", ".join(["{}: {}".format(k, offset[0]['offsets'][k]) for k in  offset[0]['offsets']])))
                labware.set_offset(**offset[0]['offsets'])
            else:
                if self._ctx.is_simulating():
                    self.logger.warning("None or multiple offset definition found for labware {}: {}".format(labware.load_name, offset))
                else:
                    raise Exception("None or multiple offset definition found for labware {}: {}".format(labware.load_name, offset))

    def load_json_from_file(self, filepath):
        self.logger.info("Opening file for json: {}".format(filepath))
        with open(filepath, "r") as f:
            return json.load(f)

    @property
    def current_directory(self):
        """ Get the current directory in which the class is defined.
            Each subclass will have the corresponding directory
        """
        return os.path.split(inspect.getsourcefile(self.__class__))[0]

    def check_and_get_absolute_path(self, filename):
        """ Check if the passed variable is an absolute path.
            If it is not absolute it will concatenate it with the current module directory
            :param filename: a filename or an absolute path
            :return the same as input if it is an absolute path or the passed input concatenated with the current folder
        """
        if not os.path.isabs(filename):
            abspath = os.path.join(self.current_directory, filename)
        else:
            abspath = filename
        self.logger.debug("Absolute path: File {} returning path {}".format(filename, abspath))
        return abspath

    def load_flow_rate(self, name=None):
        """ Load a defined flow rate configuration
            Data is stored in the json file passed to the *load_from_json* function of the FlowRates class.
            **Note**: you must use *apply_flow_rate* to make the loaded flow rate effective
            :param name: the identifier of the flow rate in the json file.
        """
        self._current_flow_rate = self._flow_rates.default_flow_rate if name is None else self._flow_rates.get(name)

    def apply_flow_rate(self, pipette, name=None, multiplier=1.0):
        """ Apply the saved flow rate multiplied by *multiplier* to the passed pipette;
            :param pipette: the pipette to apply the flow rates to;
            :param name: the identifier of the flow rate in the json file;
            :param multiplier: a multiplier for the saved flow rate in order to have percentages of saved flow rates.
        """
        self.logger.info(pipette)

        defaults_flow_rate = self._flow_rates.get_defaults(pipette.name)
        flow_rate = self._current_flow_rate if name is None else self._flow_rates.get(name)

        for f in flow_rate:
            self.logger.info("Applying flow rate {}: {}".format(f, flow_rate[f]))
            if flow_rate[f] is not None:
                to_set = flow_rate[f] * multiplier
            else:
                to_set = defaults_flow_rate[f]
            setattr(pipette.flow_rate, f, to_set)

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

    def load_labware_with_offset(
        self,
        load_name: str,
        location: types.DeckLocation,
        label: Optional[str] = None,
        namespace: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Labware:
        """ Wrapper to ease labware loading and offset setting for running with opentrons_execute"""
        labware = self._ctx.load_labware(load_name, location, label, namespace, version)
        self.apply_offset_to_labware(labware)
        return labware

    def _load_reagent_plate(self):
        self.logger.info("Initializing Reagent plate helper")
        available_cols_for_reagent = max(0, 12-self._pcr_mastermix_with_index_col_offset)
        self.logger.info("Reagent plate has {} columns available.".format(available_cols_for_reagent))
        
        self._reagent_plate_helper = ReagentPlateHelper(self.num_samples_in_rows,
                                                        well_volume_limit=self._reagent_plate_max_volume,
                                                        num_cols=available_cols_for_reagent)
        for r in self.recipes:
            if r.use_reagent_plate:
                self._reagent_plate_helper.assign_reagent(r.name, r.volume_to_distribute, r.volume_available)

    def load_wash_plate_in_slot(self, slot):
        self.logger.info("Initializing Wash plate helper on slot {}".format(slot))
        plate = self.load_labware_with_offset(self._wash_plate_labware_name, slot, "Shared wash plate")
        self._wash_plate_helper = ReagentPlateHelper(self.num_samples_in_rows, num_rows=1, well_volume_limit=self._wash_plate_max_volume)
        for r in self.recipes:
            if r.use_wash_plate:
                self._wash_plate_helper.assign_reagent(r.name, r.volume_to_distribute, r.volume_available)
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

    def get_pcr_mastermix_with_index_for_labware(self, labware):
        return [w for c in self.get_columns_for_samples(labware, self._pcr_mastermix_with_index_col_offset) for w in c][:self._num_samples]

    def get_pcr_mastermix_with_index_first_row_for_labware(self, labware):
        return [c[0] for c in self.get_columns_for_samples(labware, self._pcr_mastermix_with_index_col_offset)]

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

    @abstractmethod
    def amplify_tagmented_amplicons(self):
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

        self.set_task_name("Amplify TAG Amplicons")
        self.amplify_tagmented_amplicons()
