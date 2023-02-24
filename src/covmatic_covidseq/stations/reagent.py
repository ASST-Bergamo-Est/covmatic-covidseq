import bisect
import logging
import math
from typing import Tuple

from covmatic_stations.utils import WellWithVolume, MoveWithSpeed

from ..recipe import Recipe
from ..station import CovidseqBaseStation, instrument_loader, labware_loader
from ..pipette_chooser import PipetteChooser


class ReagentStationException(Exception):
    pass


class ReagentStation(CovidseqBaseStation):
    def __init__(self,
                 ot_name = "OT1",
                 tipracks300_slots: Tuple[str, ...] = ("9",),
                 tipracks1000_slots: Tuple[str, ...] = ("8",),
                 reagent_plate_slot="1",
                 *args, **kwargs):
        super().__init__(ot_name=ot_name, *args, **kwargs)
        self._tipracks300_slots = tipracks300_slots
        self._tipracks1000_slots = tipracks1000_slots
        self._reagent_plate_slot = reagent_plate_slot
        self._pipette_chooser = PipetteChooser()

    @labware_loader(0, "_tipracks300")
    def load_tipracks300(self):
        self._tipracks300 = [
            self._ctx.load_labware('opentrons_96_filtertiprack_200ul', slot, '200ul filter tiprack')
            for slot in self._tipracks300_slots]

    @labware_loader(0, "_tipracks1000")
    def load_tipracks1000(self):
        self._tipracks1000 = [
            self._ctx.load_labware('opentrons_96_filtertiprack_1000ul', slot, '1000ul filter tiprack')
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
        self._empty_tube_racks = self._ctx.load_labware('opentrons_24_tuberack_generic_2ml_screwcap', 6, 'empty tubes rack')

    @labware_loader(1, '_empty_tubes_list')
    def load_empty_tubes(self):
        available_tubes = [self._empty_tube_racks.wells_by_name()['D6']] * len(self.recipes)
        self._empty_tube_list = []
        for r, t in zip(self.recipes, available_tubes):
            self.logger.info("Recipe {} assigned to tube: {}".format(r.name, t))
            self._empty_tube_list.append({"recipe": r.name, "tube": WellWithVolume(t, 0)})

    @labware_loader(2, '_reagent_plate')
    def load_reagent_plate(self):
        self._reagent_plate = self.load_reagents_plate(self._reagent_plate_slot)

    @labware_loader(3, '_cdna1_plate')
    def load_cdna1_plate(self):
        self._cdna1_plate = self._ctx.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 2, 'empty tubes rack')

    def _tipracks(self) -> dict:
        return {
            '_tipracks300': '_p300',
            '_tipracks1000': '_p1000'
        }

    def get_tube_for_recipe(self, recipe):
        """ Get reagent for prepared mix """
        self.logger.info("Getting tube for recipe {}".format(recipe))
        for e in self._empty_tube_list:
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
        self.logger.info("Filling reagent plate with {}".format(reagent_name))
        source = self.get_tube_for_recipe(reagent_name)

        remaining_wells_with_volume = self.reagent_plate_helper.get_wells_with_volume(reagent_name)

        total_volume_to_aspirate = sum([v for (_, v) in remaining_wells_with_volume])
        self.logger.info("Total volume for {} samples is {}".format(self._num_samples, total_volume_to_aspirate))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(total_volume_to_aspirate)

        if disposal_volume is None:
            disposal_volume = pipette.min_volume / 2

        self.logger.info("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        pipette_available_volume = self._pipette_chooser.get_max_volume(pipette) - disposal_volume

        for i, (dest_well, volume) in enumerate(remaining_wells_with_volume):
            if not self.run_stage("Distribute {} {}/{}".format(reagent_name, i+1, len(remaining_wells_with_volume))):
                if isinstance(source, WellWithVolume):
                    source.extract_vol_and_get_height(volume)
            else:
                num_transfers = math.ceil(volume/pipette_available_volume)
                self.logger.info("We need {} transfer with {:.1f}ul pipette".format(num_transfers, self._pipette_chooser.get_max_volume(pipette)))

                dest_well_with_volume = WellWithVolume(dest_well, 0)

                if not pipette.has_tip:
                    self.pick_up(pipette)

                while volume > 0:
                    self.logger.info("Remaining volume: {:1f}".format(volume))
                    volume_to_transfer = min(volume, pipette_available_volume)
                    self.logger.info("Transferring volume {:1f} for well {}".format(volume_to_transfer, dest_well))
                    if (pipette.current_volume - disposal_volume) < volume_to_transfer:
                        total_remaining_volume = min(pipette_available_volume,
                                               sum([v for (_, v) in remaining_wells_with_volume[i:]])) - (pipette.current_volume - disposal_volume)
                        self.logger.info("Volume not enough, aspirating {:.1f}ul".format(total_remaining_volume))

                        if isinstance(source, WellWithVolume):
                            well = source.well
                            aspirate_height = source.extract_vol_and_get_height(total_remaining_volume)
                        else:
                            well = source
                            aspirate_height = 0.5

                        with MoveWithSpeed(pipette,
                                           from_point=well.bottom(aspirate_height + 5),
                                           to_point=well.bottom(aspirate_height),
                                           speed=self._slow_vertical_speed, move_close=False):
                            pipette.aspirate(total_remaining_volume)

                    dest_well_with_volume.fill(volume_to_transfer)
                    self.logger.info("Dispensing at {}".format(dest_well_with_volume.height))

                    with MoveWithSpeed(pipette,
                                       from_point=dest_well.bottom(dest_well_with_volume.height + 2.5),
                                       to_point=dest_well.bottom(dest_well_with_volume.height),
                                       speed=self._slow_vertical_speed, move_close=False):
                        pipette.dispense(volume_to_transfer)
                    volume -= volume_to_transfer
                    self.logger.info("Final volume in tip: {}ul".format(pipette.current_volume))

        if pipette.has_tip:
            self.drop(pipette)

    def fill_wells(self, reagent_name, wells, pipette=None, disposal_volume=None):
        """ Distribute reagent prepared for recipe passed to wells.
            :param reagent_name: name of the recipe to be distributed
            :param wells: a list of well to fill
            :param pipette: the pipette to use. If None the right pipette will be used based on volume to distribute
            :param disposal_volume: the volume to be kept in pipette to have an equal volume in each well.
                                    If None it is set to the half of the pipette minimum volume
        """
        self.logger.info("Reagent {} filling wells {}".format(reagent_name, wells))

        source = self.get_tube_for_recipe(reagent_name)
        recipe = self.get_recipe(reagent_name)
        total_volume_to_aspirate = len(wells) * recipe.volume_final
        self.logger.info("Total volume for {} wells is {}".format(len(wells), total_volume_to_aspirate))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(total_volume_to_aspirate)

        if disposal_volume is None:
            disposal_volume = pipette.min_volume / 2
        self.logger.info("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        pipette_available_volume = self._pipette_chooser.get_max_volume(pipette) - disposal_volume

        for i, dest_well in enumerate(wells):
            volume = recipe.volume_final

            if not self.run_stage("Distribute {} {}/{}".format(reagent_name, i + 1, len(wells))):
                if isinstance(source, WellWithVolume):
                    source.extract_vol_and_get_height(volume)
            else:
                num_transfers = math.ceil(volume / pipette_available_volume)
                self.logger.info("We need {} transfer with {:.1f}ul pipette".format(num_transfers,
                                                                                    self._pipette_chooser.get_max_volume(
                                                                                        pipette)))

                dest_well_with_volume = WellWithVolume(dest_well, 0)

                if not pipette.has_tip:
                    self.pick_up(pipette)

                while volume > 0:
                    self.logger.info("Remaining volume: {:1f}".format(volume))
                    volume_to_transfer = min(volume, pipette_available_volume)
                    self.logger.info("Transferring volume {:1f} for well {}".format(volume_to_transfer, dest_well))
                    if (pipette.current_volume - disposal_volume) < volume_to_transfer:
                        total_remaining_volume = min(pipette_available_volume,
                                                     len(wells)-i) - (
                                                             pipette.current_volume - disposal_volume)
                        self.logger.info("Volume not enough, aspirating {:.1f}ul".format(total_remaining_volume))

                        if isinstance(source, WellWithVolume):
                            well = source.well
                            aspirate_height = source.extract_vol_and_get_height(total_remaining_volume)
                        else:
                            well = source
                            aspirate_height = 0.5

                        with MoveWithSpeed(pipette,
                                           from_point=well.bottom(aspirate_height + 5),
                                           to_point=well.bottom(aspirate_height),
                                           speed=self._slow_vertical_speed, move_close=False):
                            pipette.aspirate(total_remaining_volume)

                    dest_well_with_volume.fill(volume_to_transfer)
                    self.logger.info("Dispensing at {}".format(dest_well_with_volume.height))

                    with MoveWithSpeed(pipette,
                                       from_point=dest_well.bottom(dest_well_with_volume.height + 2.5),
                                       to_point=dest_well.bottom(dest_well_with_volume.height),
                                       speed=self._slow_vertical_speed, move_close=False):
                        pipette.dispense(volume_to_transfer)
                    volume -= volume_to_transfer
                    self.logger.info("Final volume in tip: {}ul".format(pipette.current_volume))

        if pipette.has_tip:
            self.drop(pipette)

    def prepare(self, recipe_name):
        if self.run_stage("Prepare {}".format(recipe_name)):
            recipe = self.get_recipe(recipe_name)
            tube = self.get_tube_for_recipe(recipe_name)
            volume = self.get_volume_to_transfer(recipe) * self._num_samples
            tube.fill(volume)
            self.pause("Place tube {} in {} with volume {}".format(recipe_name, tube, volume), home=False)

    def distribute_reagent(self, recipe_name, pipette=None):
        self.fill_reagent_plate(recipe_name, pipette)

    def distribute(self, recipe_name, wells, pipette=None):
        self.fill_wells(recipe_name, wells, pipette)

    def anneal_rna(self):
        self.prepare("EPH3")
        self.distribute("EPH3", self.get_samples_wells_for_labware(self._cdna1_plate))
        self.robot_pick_plate("SLOT1", "CDNA1_FULL")

    def first_strand_cdna(self):
        self.robot_drop_plate("SLOT1", "REAGENT_EMPTY")
        self.prepare("FS Mix")
        self.distribute_reagent("FS Mix", self._p300)
        self.robot_pick_plate("SLOT1", "REAGENT_FULL")

    def body(self):
        self.anneal_rna()
        self.first_strand_cdna()


    def sample_arranger(self, num_samples):
        samples = list(range(0, num_samples))
        print("Samples test: {}".format(samples[1::8]))
        # num_cols = math.ceil(self._num_samples/8)
        # print(samples)
        # print("num cols: {}".format(num_cols))
        # for i in range(num_cols):
        #     start_index = i*8
        #     end_index = min(num_samples - 1, i*8 + 8)
        #     print("Start index: {}".format(start_index))
        #     print("end_index: {}".format(end_index))
        #     print(samples[start_index:end_index])

        # samples_8 = [samples[i*8:min(self._num_samples, (i*8+8))] for i in range(math.ceil(self._num_samples/8))]
        # print("samples8: {}".format(samples_8))

if __name__ == "__main__":
    ReagentStation(num_samples=96, metadata={'apiLevel': '2.7'}).simulate()
