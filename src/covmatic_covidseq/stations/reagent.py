import bisect
import json
import logging
import math
import os
from typing import Tuple, Union

from covmatic_stations.multi_tube_source import MultiTubeSource
from covmatic_stations.utils import WellWithVolume, MoveWithSpeed
from opentrons.protocol_api import Well, ProtocolContext

from ..recipe import Recipe
from ..station import CovidseqBaseStation, instrument_loader, labware_loader, ReagentPlateException
from ..pipette_chooser import PipetteChooser
from ..utils import default_index_order


class TransferManager:
    def __init__(self, pick_function, drop_function, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._pick_function = pick_function
        self._drop_function = drop_function
        # Initialization of variable done afterward
        self._pipette = None
        self._total_volume_to_transfer = 0
        self._pipette_max_volume = 0
        self._pipette_air_gap = 0
        self._vertical_speed = 0

    def setup_transfer(self, pipette, pipette_max_volume, pipette_air_gap, total_volume_to_transfer, vertical_speed):
        self._pipette = pipette
        self._total_volume_to_transfer = total_volume_to_transfer
        self._pipette_max_volume = pipette_max_volume
        self._pipette_air_gap = pipette_air_gap
        self._vertical_speed = vertical_speed

    def transfer(self, source: Union[Well, MultiTubeSource],
                 destination: Well,
                 volume: float,
                 disposal_volume: float = 0,
                 change_tip: bool = False):

        pipette_available_volume = self._pipette_max_volume - disposal_volume

        num_transfers = math.ceil(volume / pipette_available_volume)
        self._logger.debug("We need {} transfer with {:.1f}ul pipette".format(num_transfers, self._pipette_max_volume))

        dest_well_with_volume = WellWithVolume(destination, 0)

        while volume > 0:
            if not self._pipette.has_tip:
                self._pick_function(self._pipette)

            self._logger.debug("Remaining volume: {:1f}".format(volume))
            volume_to_transfer = min(volume, pipette_available_volume)
            self._logger.debug("Transferring volume {:1f} for well {}".format(volume_to_transfer, destination))
            if (self._pipette.current_volume - disposal_volume) < volume_to_transfer:
                total_remaining_volume = min(pipette_available_volume, self._total_volume_to_transfer) - (
                        self._pipette.current_volume - disposal_volume)
                self._logger.debug("Volume not enough, aspirating {:.1f}ul".format(total_remaining_volume))
                self._aspirate(source, total_remaining_volume)

            dest_well_with_volume.fill(volume_to_transfer)
            self._logger.debug("Dispensing at {}".format(dest_well_with_volume.height))

            with MoveWithSpeed(self._pipette,
                               from_point=destination.bottom(dest_well_with_volume.height + 2.5),
                               to_point=destination.bottom(dest_well_with_volume.height),
                               speed=self._vertical_speed, move_close=False):
                self._pipette.dispense(volume_to_transfer)
            volume -= volume_to_transfer
            self._total_volume_to_transfer -= volume_to_transfer
            self._logger.debug("Final volume in tip: {}ul".format(self._pipette.current_volume))

            if change_tip and self._pipette.has_tip:
                self._drop_function(self._pipette)

    def _aspirate(self, source, volume):
        if isinstance(source, MultiTubeSource):
            self._aspirate_from_mts(source, volume)
        else:
            self._aspirate_from_source(source, volume)

    def _aspirate_from_mts(self, source: MultiTubeSource, volume):
        self._logger.info("Aspirating from multi tube source {} {}ul".format(source, volume))
        source.prepare_aspiration(volume)
        source.aspirate(self._pipette)

    def _aspirate_from_source(self, source, volume):
        self._logger.info("Aspirating from {} {}ul".format(source, volume))
        if isinstance(source, WellWithVolume):
            well = source.well
            aspirate_height = source.extract_vol_and_get_height(volume)
        else:
            well = source
            aspirate_height = 0.5

        with MoveWithSpeed(self._pipette,
                           from_point=well.bottom(aspirate_height + 5),
                           to_point=well.bottom(aspirate_height),
                           speed=self._vertical_speed, move_close=False):
            self._pipette.aspirate(volume)

class ReagentStationException(Exception):
    pass


class ReagentStation(CovidseqBaseStation):
    def __init__(self,
                 ot_name = "OT1",
                 tipracks300_slots: Tuple[str, ...] = ("9",),
                 tipracks1000_slots: Tuple[str, ...] = ("8",),
                 reagent_plate_slot="1",
                 cdna1_plate_slot="2",
                 cov12_plate_slot="3",
                 tag1_plate_slot="4",
                 wash_plate_slot="5",
                 index_plate_slot="7",
                 reagents_tempdeck_slot="10",
                 reagent_chilled_tubes_json="reagents_chilled_tubes.json",
                 reagents_wash_slot="11",
                 disposal_volume_ratio=0.25,
                 index_list=None,
                 *args, **kwargs):
        super().__init__(ot_name=ot_name, *args, **kwargs)
        self._tipracks300_slots = tipracks300_slots
        self._tipracks1000_slots = tipracks1000_slots
        self._reagent_plate_slot = reagent_plate_slot
        self._cdna1_plate_slot = cdna1_plate_slot
        self._cov12_plate_slot = cov12_plate_slot
        self._tag1_plate_slot = tag1_plate_slot
        self._wash_plate_slot = wash_plate_slot
        self._index_plate_slot = index_plate_slot
        self._reagents_tempdeck_slot = reagents_tempdeck_slot
        self._reagents_wash_slot = reagents_wash_slot
        self._disposal_volume_ratio = disposal_volume_ratio
        self._pipette_chooser = PipetteChooser()
        self._tubes_list = []
        self._reagents_chilled_tubes = []
        self.load_reagents_chilled_tubes_json(reagent_chilled_tubes_json)
        self._index_list = index_list
        self._transfer_manager = TransferManager(self.pick_up, self.drop)

    def pre_loaders_initializations(self):
        super().pre_loaders_initializations()
        self.check_index_list()

    def check_index_list(self):
        self.logger.info("Checking index list {}".format(self._index_list))

        if self._index_list is None or len(self._index_list) < self._num_samples:
            if self._ctx.is_simulating():
                self.logger.warning("Index list passed is None or not enough; assigning default list for simulation.")
                self._index_list = default_index_order
            else:
                if self._index_list is None:
                    message = "No index list passed. You must specify at least {} index".format(self._num_samples)
                else:
                    message = "Not enough index passed. Passed {} index, needed {}".format(len(self._index_list), self._num_samples)
                raise Exception(message)

    def load_reagents_chilled_tubes_json(self, filename):
        abspath = self.check_and_get_absolute_path(filename)
        self.logger.info("Loading reagents chilled tubes from {}".format(abspath))

        with open(abspath, "r") as f:
            self._reagents_chilled_tubes = json.load(f)

    @labware_loader(0, "_tipracks300")
    def load_tipracks300(self):
        self._tipracks300 = [
            self.load_labware_with_offset('opentrons_96_filtertiprack_200ul', slot, '200ul filter tiprack')
            for slot in self._tipracks300_slots]

    @labware_loader(0, "_tipracks1000")
    def load_tipracks1000(self):
        self._tipracks1000 = [
            self.load_labware_with_offset('opentrons_96_filtertiprack_1000ul', slot, '1000ul filter tiprack')
            for slot in self._tipracks1000_slots]

    @instrument_loader(0, '_p300')
    def load_p300(self):
        self._p300 = self._ctx.load_instrument('p300_single_gen2', 'right', tip_racks=self._tipracks300)
        self._pipette_chooser.register(self._p300, 200)

    @instrument_loader(0, '_p1000')
    def load_p1000(self):
        self._p1000 = self._ctx.load_instrument('p1000_single_gen2', 'left', tip_racks=self._tipracks1000)
        self._pipette_chooser.register(self._p1000, 1000)

    @labware_loader(0, '_empty_tube_racks')
    def load_empty_tube_racks(self):
        self._empty_tube_racks = self.load_labware_with_offset('opentrons_24_tuberack_generic_2ml_screwcap', 6, 'empty tubes rack')

    @labware_loader(1, '_empty_tubes_list')
    def load_empty_tubes(self):
        available_tubes = self._empty_tube_racks.wells()
        for r, t in zip(filter(lambda x: x.needs_empty_tube, self.recipes), available_tubes):
            self.append_tube_for_recipe(r.name, t, 0)

    @labware_loader(1, '_reagents_tempdeck')
    def load_reagents_tempdeck(self):
        self._reagents_tempdeck = self._ctx.load_module('temperature module gen2', self._reagents_tempdeck_slot)

    def append_tube_for_recipe(self, recipe_name, well, volume=None):
        r = self.get_recipe(recipe_name)

        if volume is None:
            volume = self.get_volume_to_transfer(r) * self._num_samples

        self.logger.info("Recipe {} assigned to tube: {}; volume: {}".format(r.name, well, volume))
        self._tubes_list.append({"recipe": recipe_name, "tube": WellWithVolume(well, volume)})

    @labware_loader(1, '_reagents_tubes')
    def load_reagents_tubes(self):
        self._reagents_chilled = self._reagents_tempdeck.load_labware('opentrons_24_aluminumblock_generic_2ml_screwcap',
                                                                    'Reagents tube')

        self.apply_offset_to_labware(self._reagents_chilled)

        for rct in self._reagents_chilled_tubes:
            recipe = self.get_recipe(rct["name"])
            if not recipe.needs_empty_tube:
                self.append_tube_for_recipe(recipe.name, self._reagents_chilled.wells_by_name()[rct["well"]])

    @labware_loader(1, '_reagents_wash_tubes')
    def load_reagents_wash_tubes(self):
        self._reagents_wash = self.load_labware_with_offset('opentrons_6_tuberack_falcon_50ml_conical',
                                                     self._reagents_wash_slot,
                                                     'wash reagents tubes')
        self.append_tube_for_recipe("TWB", self._reagents_wash.wells_by_name()['A1'])

    @labware_loader(2, '_reagent_plate')
    def load_reagent_plate(self):
        self._reagent_plate = self.load_labware_with_offset('nest_96_wellplate_100ul_pcr_full_skirt',
                                                   self._reagent_plate_slot, 'shared reagent plate')

    @labware_loader(2, '_wash_plate')
    def load_wash_plate(self):
        self._wash_plate = self.load_wash_plate_in_slot(self._wash_plate_slot)

    @labware_loader(3, '_cdna1_plate')
    def load_cdna1_plate(self):
        self._cdna1_plate = self.load_labware_with_offset('nest_96_wellplate_100ul_pcr_full_skirt',
                                                   self._cdna1_plate_slot, 'empty plate for CDNA1')

    @labware_loader(4, '_cov12_plate')
    def load_cov12_plate(self):
        self._cov12_plate = self.load_labware_with_offset('nest_96_wellplate_100ul_pcr_full_skirt',
                                                   self._cov12_plate_slot, 'empty plate for COV1 COV2')

    @labware_loader(5, '_tag1_plate')
    def load_tag1_plate(self):
        self._tag1_plate = self.load_labware_with_offset('nest_96_wellplate_100ul_pcr_full_skirt',
                                                   self._tag1_plate_slot, 'empty plate for TAG1')

    @labware_loader(6, '_index_plate')
    def load_index_plate(self):
        self._index_plate = self.load_labware_with_offset('nest_96_wellplate_100ul_pcr_full_skirt',
                                                         self._index_plate_slot, 'Index plate')

    def _tipracks(self) -> dict:
        return {
            '_tipracks300': '_p300',
            '_tipracks1000': '_p1000'
        }

    def get_tube_for_recipe(self, recipe):
        """ Get reagent for prepared mix """
        self.logger.info("Getting tube for recipe {}".format(recipe))
        for e in self._tubes_list:
            if e["recipe"] == recipe:
                self.logger.info("Found {}".format(e["tube"]))
                return e["tube"]
        raise ReagentStationException("Recipe {} has no tube assigned".format(recipe))

    def get_volume_to_transfer(self, r: Recipe) -> float:
        ret = r.volume_to_distribute
        self.logger.info("Volume to transfer to plate for recipe {} is {}".format(r.name, ret))
        return ret

    def fill_reagent_plate(self, reagent_name, pipette=None, disposal_volume=None):
        """ Fill the reagent plate with the named reciped passed.
            :param reagent_name: the recipe name to distribute
            :param pipette: the pipette to use. If None the pipette will be choosed based on volume to distribute
            :param disposal_volume: the volume to be kept in pipette to have an equal volume in each well.
                                    If None it is set to the half of the pipette minimum volume
        """
        source = self.get_tube_for_recipe(reagent_name)
        dest_wells_with_volume = self.reagent_plate_helper.get_wells_with_volume(reagent_name, self._reagent_plate)

        self.logger.info("Filling reagent plate with {}".format(reagent_name))
        self.fill_shared_plate(reagent_name, source, dest_wells_with_volume, pipette, disposal_volume)

    def fill_wash_plate(self, reagent_name, pipette=None, disposal_volume=None):
        source = self.get_tube_for_recipe(reagent_name)
        dest_wells_with_volume = self.wash_plate_helper.get_wells_with_volume(reagent_name, self._wash_plate)

        self.logger.info("Filling wash plate with {}".format(reagent_name))
        self.fill_shared_plate(reagent_name, source, dest_wells_with_volume, pipette, disposal_volume)

    def fill_shared_plate(self, reagent_name, source, dest_wells_with_volume, pipette=None, disposal_volume=None):
        total_volume_to_aspirate = sum([v for (_, v) in dest_wells_with_volume])
        self.logger.info("Filling shared plate with reagent {}".format(reagent_name))
        self.logger.debug("Total volume for {} samples is {}".format(self._num_samples, total_volume_to_aspirate))
        self.logger.debug("Destinations received: {}".format(dest_wells_with_volume))
        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(total_volume_to_aspirate)

        if disposal_volume is None:
            disposal_volume = pipette.min_volume * self._disposal_volume_ratio

        self.logger.debug("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        self._transfer_manager.setup_transfer(pipette,
                                              self._pipette_chooser.get_max_volume(pipette),
                                              self._pipette_chooser.get_air_gap(pipette),
                                              total_volume_to_aspirate,
                                              self._slow_vertical_speed)

        for i, (dest_well, volume) in enumerate(dest_wells_with_volume):
            if not self.run_stage(
                    self.build_stage("Dist. {} {}/{}".format(reagent_name, i + 1, len(dest_wells_with_volume)))):
                if isinstance(source, WellWithVolume):
                    source.extract_vol_and_get_height(volume)
            else:
                self._transfer_manager.transfer(source, dest_well, volume, disposal_volume)

        if pipette.has_tip:
            self.drop(pipette)

    def fill_wells(self, source, volume, wells, pipette=None, disposal_volume=None, stage="Dist."):
        """ Distribute reagent prepared for recipe passed to wells.
            :param reagent_name: name of the recipe to be distributed
            :param wells: a list of well to fill
            :param pipette: the pipette to use. If None the right pipette will be used based on volume to distribute
            :param disposal_volume: the volume to be kept in pipette to have an equal volume in each well.
                                    If None it is set to the half of the pipette minimum volume
        """
        self.logger.info("Filling wells {} using {}".format(source, wells))

        total_volume_to_aspirate = len(wells) * volume
        self.logger.debug("Total volume for {} wells is {}".format(len(wells), total_volume_to_aspirate))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(total_volume_to_aspirate)

        if disposal_volume is None:
            disposal_volume = pipette.min_volume * self._disposal_volume_ratio
        self.logger.debug("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        self._transfer_manager.setup_transfer(pipette,
                                              self._pipette_chooser.get_max_volume(pipette),
                                              self._pipette_chooser.get_air_gap(pipette),
                                              total_volume_to_aspirate,
                                              self._slow_vertical_speed)

        for i, dest_well in enumerate(wells):
            if not self.run_stage(self.build_stage("{} {}/{}".format(stage, i + 1, len(wells)))):
                if isinstance(source, WellWithVolume):
                    source.extract_vol_and_get_height(volume)
            else:
                self._transfer_manager.transfer(source, dest_well, volume, disposal_volume)

        if pipette.has_tip:
            self.drop(pipette)

    def prepare(self, recipe_name):
        if self.run_stage(self.build_stage("Prep. {}".format(recipe_name))):
            recipe = self.get_recipe(recipe_name)
            tube = self.get_tube_for_recipe(recipe_name)
            if recipe.needs_empty_tube:
                tube.fill(recipe.total_prepared_vol * self._num_samples)            # We should prepare recipe here
            self.pause("Place tube {} in {}".format(recipe_name, tube), home=False)

    def distribute_reagent(self, recipe_name, pipette=None):
        self.fill_reagent_plate(recipe_name, pipette)

    def distribute(self, recipe_name, wells, pipette=None, disposal_volume=None):
        source = self.get_tube_for_recipe(recipe_name)
        recipe = self.get_recipe(recipe_name)
        self.fill_wells(source, recipe.volume_final, wells, pipette, disposal_volume=disposal_volume)

    def distribute_index_to_wells(self, destination_wells, index_volume=10):
        all_wells = self._index_plate.wells_by_name()
        sources = [all_wells[idx] for idx in self._index_list]
        self.logger.info("Index sources are: {}".format(sources))

        pipette = self._pipette_chooser.get_pipette(index_volume, consider_air_gap=True)

        well_initial_vol = self.get_recipe("PCR Mix").volume_final

        for i, (s, d) in enumerate(zip(sources, destination_wells)):
            if self.run_stage(self.build_stage("index {}/{}".format(i+1, len(destination_wells)))):
                dest_with_volume = WellWithVolume(d, well_initial_vol)

                self.logger.info("Transferring index from {} to {}".format(s, d))

                self.pick_up(pipette)
                pipette.move_to(s.top())
                pipette.move_to(s.bottom(0.5), speed=self._very_slow_vertical_speed)
                pipette.aspirate(index_volume)
                pipette.move_to(s.top(), speed=self._very_slow_vertical_speed)
                pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))

                pipette.move_to(d.top())
                pipette.dispense(self._pipette_chooser.get_air_gap(pipette))
                dest_with_volume.fill(index_volume)
                with MoveWithSpeed(pip=pipette,
                                   from_point=d.top(),
                                   to_point=d.bottom(dest_with_volume.height),
                                   speed=self._slow_vertical_speed):
                    pipette.dispense(index_volume)
                pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))

                self.drop(pipette)

    def anneal_rna(self):
        self.prepare("EPH3")
        self.distribute("EPH3", self.get_samples_wells_for_labware(self._cdna1_plate), self._p300)
        self.robot_pick_plate("SLOT{}".format(self._cdna1_plate_slot), "CDNA1_FULL")

    def first_strand_cdna(self):
        self.prepare("FS Mix")
        self.distribute_reagent("FS Mix", self._p300)
        self.robot_pick_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")
        self.robot_drop_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_EMPTY")

    def amplify_cdna(self):
        self.prepare("CPP1 Mix")
        self.prepare("CPP2 Mix")
        self.distribute("CPP1 Mix", self.get_samples_COV1_for_labware(self._cov12_plate), self._p300)
        self.distribute("CPP2 Mix", self.get_samples_COV2_for_labware(self._cov12_plate), self._p300)
        self.robot_pick_plate("SLOT{}".format(self._cov12_plate_slot), "COV12_FULL")

    def tagment_pcr_amplicons(self):
        self.prepare("TAG Mix")
        self.distribute("TAG Mix", self.get_samples_wells_for_labware(self._tag1_plate), self._p300)
        self.robot_pick_plate("SLOT{}".format(self._tag1_plate_slot), "TAG1_FULL")

    def post_tagmentation_cleanup(self):
        self.prepare("ST2")
        self.prepare("TWB")
        self.distribute_reagent("ST2", self._p300)
        self.robot_pick_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")

        self.fill_wash_plate("TWB")
        self.robot_drop_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_EMPTY")
        self.robot_pick_plate("SLOT{}WASH".format(self._wash_plate_slot), "WASH_FULL")

    def amplify_tagmented_amplicons(self):
        pcr_mm_and_index_wells = self.get_pcr_mastermix_with_index_for_labware(self._reagent_plate)
        self.prepare("PCR Mix")
        self.distribute("PCR Mix", pcr_mm_and_index_wells, self._p300)
        self.distribute_index_to_wells(pcr_mm_and_index_wells)


if __name__ == "__main__":
    ReagentStation(num_samples=96, metadata={'apiLevel': '2.7'}).simulate()
