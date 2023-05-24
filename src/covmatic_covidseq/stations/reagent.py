import bisect
import json
import logging
import math
import os
from typing import Tuple, Union

from covmatic_stations.multi_tube_source import MultiTubeSource
from covmatic_stations.utils import WellWithVolume, MoveWithSpeed
from opentrons.protocol_api import Well, ProtocolContext

from ..transfer_manager import TransferManager
from ..recipe import Recipe
from ..station import CovidseqBaseStation, instrument_loader, labware_loader, ReagentPlateException
from ..pipette_chooser import PipetteChooser
from ..utils import default_index_order



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
                 reagent_json="reagents.json",
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
        self._reagents_tubes = []
        self.load_reagents_tubes_json(reagent_json)
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

    def load_reagents_tubes_json(self, filename):
        abspath = self.check_and_get_absolute_path(filename)
        self.logger.info("Loading reagents chilled tubes from {}".format(abspath))

        with open(abspath, "r") as f:
            self._reagents_tubes = json.load(f)

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

    def append_tube_for_reagent(self, reagent_name, well, volume):
        self.logger.info("Reagent {} assigned to tube: {}; volume: {}".format(reagent_name, well, volume))
        self._tubes_list.append({"recipe": reagent_name, "tube": WellWithVolume(well, volume)})

    @labware_loader(2, '_reagents_chilled')
    def load_reagents_chilled(self):
        self._reagents_chilled = self._reagents_tempdeck.load_labware('opentrons_24_aluminumblock_generic_2ml_screwcap',
                                                                    'Reagents tube')
        self.apply_offset_to_labware(self._reagents_chilled)

    @labware_loader(2, '_reagents_wash_tubes')
    def load_reagents_wash_tubes(self):
        self._reagents_wash = self.load_labware_with_offset('opentrons_6_tuberack_falcon_50ml_conical',
                                                     self._reagents_wash_slot,
                                                     'wash reagents tubes')
        # self.append_tube_for_recipe("TWB", self._reagents_wash.wells_by_name()['A1'])

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

    def load_tubes(self):
        reagents_list = {}

        for recipe in self.recipes:
            self.logger.info("Loading reagents for recipe {}".format(recipe.name))

            if recipe.needs_empty_tube:
                for step in recipe.steps:
                    reagent_name = step["reagent"]
                    reagent_volume = step["vol"] * self._num_samples

                    if reagent_name in reagents_list:
                        self.logger.info(
                            "Reagent {} already present, adding volume {}".format(reagent_name, reagent_volume))
                        reagents_list[reagent_name]["volume"] += reagent_volume
                    else:
                        self.logger.info(
                            "Reagent {} adding in list with volume {}".format(reagent_name, reagent_volume))
                        reagents_list[reagent_name] = {"volume": reagent_volume}

            else:
                self.append_tube_for_recipe(recipe.name, self._get_reagent_tube_from_name(recipe.name))

        self.logger.info("Reagents loaded: {}".format(reagents_list))
        for reagent in reagents_list:
            self.append_tube_for_reagent(reagent, self._get_reagent_tube_from_name(reagent), reagents_list[reagent]["volume"])

    def _get_reagent_tube_from_name(self, name):
        self.logger.info("Searching tube for reagent {}".format(name))
        found_tubes = list(filter(lambda x: x["name"] == name, self._reagents_tubes))

        if len(found_tubes) > 1:
            raise Exception("Multiple reagent tubes found for reagent {}: {}".format(name, found_tubes))
        if len(found_tubes) < 1:
            raise Exception("None reagent tubes found for reagent {}".format(name, found_tubes))

        well_position = found_tubes[0]["well"]

        if found_tubes[0]["plate"] == "chilled tubes":
            plate = self._reagents_chilled
        elif found_tubes[0]["plate"] == "wash":
            plate = self._reagents_wash
        else:
            raise Exception("Plate {} unknown".format(found_tubes[0]["plate"]))

        well = plate.wells_by_name()[well_position]

        self.logger.info("Reagent {} returning well {}".format(name, well))
        return well

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

    def fill_shared_plate(self, reagent_name, source, dest_wells_with_volume,
                          pipette=None, disposal_volume=None, use_air_gap=False):
        total_volume_to_aspirate = sum([v for (_, v) in dest_wells_with_volume])
        self.logger.info("Filling shared plate with reagent {}".format(reagent_name))
        self.logger.info("Total volume for {} samples is {}".format(self._num_samples, total_volume_to_aspirate))
        self.logger.info("Destinations received: {}".format(dest_wells_with_volume))
        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(total_volume_to_aspirate)

        if disposal_volume is None:
            disposal_volume = pipette.min_volume * self._disposal_volume_ratio

        self.logger.info("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        self._transfer_manager.setup_transfer(pipette,
                                              self._pipette_chooser.get_max_volume(pipette),
                                              self._pipette_chooser.get_air_gap(pipette) if use_air_gap else 0,
                                              vertical_speed=self._slow_vertical_speed,
                                              total_volume_to_transfer=total_volume_to_aspirate)

        for i, (dest_well, volume) in enumerate(dest_wells_with_volume):
            if not self.run_stage(
                    self.build_stage("Dist. {} {}/{}".format(reagent_name, i + 1, len(dest_wells_with_volume)))):
                if isinstance(source, WellWithVolume):
                    source.extract_vol_and_get_height(volume)
            else:
                self._transfer_manager.transfer(source, dest_well, volume, disposal_volume)

        if pipette.has_tip:
            self.drop(pipette)

    def fill_wells(self, source, volume, wells, pipette=None, disposal_volume=None, stage="Dist.", use_air_gap=False):
        """ Distribute reagent prepared for recipe passed to wells.
            :param reagent_name: name of the recipe to be distributed
            :param wells: a list of well to fill
            :param pipette: the pipette to use. If None the right pipette will be used based on volume to distribute
            :param disposal_volume: the volume to be kept in pipette to have an equal volume in each well.
                                    If None it is set to the half of the pipette minimum volume
        """
        self.logger.info("Filling wells {} using {}".format(wells, source))

        total_volume_to_aspirate = len(wells) * volume
        self.logger.debug("Total volume for {} wells is {}".format(len(wells), total_volume_to_aspirate))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(total_volume_to_aspirate)

        if disposal_volume is None:
            disposal_volume = pipette.min_volume * self._disposal_volume_ratio
        self.logger.debug("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        self._transfer_manager.setup_transfer(pipette,
                                              self._pipette_chooser.get_max_volume(pipette),
                                              pipette_air_gap=self._pipette_chooser.get_air_gap(pipette) if use_air_gap else 0,
                                              total_volume_to_transfer=total_volume_to_aspirate,
                                              vertical_speed=self._slow_vertical_speed)

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
            destination_tube = self.get_tube_for_recipe(recipe_name)
            mix_times = 10
            last_used_pipette = None

            if recipe.needs_empty_tube:
                for i, step in enumerate(recipe.steps):
                    last_step = (i == (len(recipe.steps) - 1))
                    volume_to_transfer = step["vol"] * self._num_samples
                    source_tube = self.get_tube_for_recipe(step["reagent"])

                    pipette = self._pipette_chooser.get_pipette(volume_to_transfer)

                    if last_used_pipette is not None and last_used_pipette.has_tip:
                        self.drop(last_used_pipette)
                    last_used_pipette = pipette

                    self._transfer_manager.setup_transfer(
                        pipette=pipette,
                        pipette_max_volume=self._pipette_chooser.get_max_volume(pipette),
                        pipette_air_gap=0,
                        vertical_speed=self._slow_vertical_speed,
                        total_volume_to_transfer=volume_to_transfer
                    )

                    self._transfer_manager.transfer(source_tube, destination_tube, volume_to_transfer)

                mix_volume = recipe.total_prepared_vol * self._num_samples * 0.8
                mix_pipette = self._pipette_chooser.get_pipette(mix_volume)

                if last_used_pipette is not None and last_used_pipette != mix_pipette and last_used_pipette.has_tip:
                    self.drop(last_used_pipette)

                self._transfer_manager.setup_transfer(mix_pipette,
                                                      self._pipette_chooser.get_max_volume(mix_pipette),
                                                      pipette_air_gap=0,
                                                      vertical_speed=self._slow_vertical_speed)
                self._transfer_manager.setup_mix(mix_times=mix_times, mix_volume=mix_volume)
                self._transfer_manager.mix(destination_tube, drop_tip=True)

                # destination_tube.fill(recipe.total_prepared_vol * self._num_samples)
            self.pause("Place tube {} in {}".format(recipe_name, destination_tube), home=False)

    def distribute_reagent(self, recipe_name, pipette=None):
        self.fill_reagent_plate(recipe_name, pipette, 5)

    def distribute(self, recipe_name, wells, pipette=None, disposal_volume=None):
        source = self.get_tube_for_recipe(recipe_name)
        recipe = self.get_recipe(recipe_name)
        self.fill_wells(source, recipe.volume_final, wells, pipette,
                        disposal_volume=disposal_volume, stage="Dist. {}".format(recipe.name))

    def distribute_index_to_wells(self, destination_wells, index_volume=10, air_gap_volume=5):
        all_wells = self._index_plate.wells_by_name()
        sources = [all_wells[idx] for idx in self._index_list]
        self.logger.info("Index sources are: {}".format(sources))

        pipette = self._pipette_chooser.get_pipette(index_volume, consider_air_gap=True)

        if not air_gap_volume:
            air_gap_volume = self._pipette_chooser.get_air_gap(pipette)

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
                pipette.air_gap(air_gap_volume)

                pipette.move_to(d.top())
                pipette.dispense(air_gap_volume)
                dest_with_volume.fill(index_volume)
                with MoveWithSpeed(pip=pipette,
                                   from_point=d.top(),
                                   to_point=d.bottom(dest_with_volume.height),
                                   speed=self._slow_vertical_speed):
                    pipette.dispense(index_volume)
                    pipette.mix(1, dest_with_volume.volume * 0.75)
                pipette.air_gap(air_gap_volume)

                self.drop(pipette)

    def body(self):
        self.load_tubes()
        super().body()

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
        """ We prepare a solution with PCR mastermix and index.
            The solution is prepared with an overhead since the OT library
            will need to transfer the solution in the sample plate.
        """
        final_index_volume = 10
        recipe_name = "PCR Mix"

        pcr_mm_and_index_wells = self.get_pcr_mastermix_with_index_for_labware(self._reagent_plate)
        recipe = self.get_recipe(recipe_name)

        self.prepare(recipe_name)

        self.fill_wells(self.get_tube_for_recipe(recipe_name),
                        recipe.volume_to_distribute,
                        pcr_mm_and_index_wells, self._p300,
                        stage="Distr. {}".format(recipe.name))

        distribute_index_volume = (1 + (recipe.volume_to_distribute - recipe.volume_final)/recipe.volume_final) * final_index_volume
        self.logger.info("Using {} ul of index for {} of {}".format(distribute_index_volume, recipe.volume_to_distribute, recipe.name))

        self.distribute_index_to_wells(pcr_mm_and_index_wells, distribute_index_volume)

        self.robot_pick_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")


class ReagentStationCalibration(ReagentStation):
    """ ReagentStationClass used for calibration.
        Since OT app v6.0.0 offsets are extracted from the runlog of the OT App run, but in this case we must not apply
        any offset to labware. Then offsets are saved in the json file *labware_offsets* and recalled in the protocol
        executed using ssh.
        Step to calibrate a protocol:
        1. load the *station_reagent_calibration.py* protocol in OT App;
        2. launch the Labware Position Check and calibrate the labware as described in the app;
        3. Run the protocol. As soon as the protocol has started you can stop it and cancel the run.
        4. Download the runlog of the executed run: offsets are stored in this file.
        5. Copy the runlog file on the robot (folder */var/lib/jupyter/notebooks/config*) using Jupyter or ssh
        6. Open a command line on the robot in the folder */var/lib/jupyter/notebooks/config*
        7. Execute the offset extractor */var/user-packages/usr/bin/covmatic-covidseq-genoffset*
        8. When requested insert the runlog filename;
        9. When requested insert the output filename *labware_offsets.json*
           The utility will create an offset json file that will be loaded when executing the ReagentStation protocol.
    """
    def __init__(self,
                 labware_load_offset=False,
                 index_list=default_index_order,
                 *args, **argv):
        super().__init__(labware_load_offset=labware_load_offset,
                         index_list=index_list,
                         *args, **argv)

if __name__ == "__main__":
    ReagentStation(num_samples=96, metadata={'apiLevel': '2.7'}).simulate()
