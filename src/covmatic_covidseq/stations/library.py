import logging
import math
from itertools import repeat, cycle, islice
from typing import Tuple

from covmatic_stations.utils import WellWithVolume, MoveWithSpeed
from opentrons.protocol_api.labware import Well
from opentrons.types import Point

from ..utils import get_labware_json_from_filename
from ..pipette_chooser import PipetteChooser
from ..station import CovidseqBaseStation, labware_loader, instrument_loader
from covmatic_stations.multi_tube_source import MultiTubeSource


def mix_well(pipette,
             well: Well,
             volume,
             repetitions,
             last_dispense_flow_rate=None,
             min_z_difference=1.0,
             travel_speed=25.0, logger=logging.getLogger()):
    """ Mix a well
        :param pipette: pipette object to use
        :param well: well to mix
        :param volume: volume to mix
        :param repetitions: number of mix (aspirate-dispense) cycles
        :param last_dispense_flow_rate: flow rate to use in the last dispense to avoid leaving liquid in tip
        :param min_z_difference: the minimum difference to have in the vertical axis
        :param travel_speed: the speed between different positions.
    """
    logger.info("Requested mix with pipette {} for well {}; repetitions {}, volume {}".format(pipette, well,
                                                                                              repetitions, volume))
    logger.info("Current pipette volume: {}".format(pipette.current_volume))

    well_with_volume = WellWithVolume(well)
    height_min = well_with_volume.height

    well_with_volume.fill(volume)
    height_max = max(well_with_volume.height, height_min + min_z_difference)

    side_movement = (well.diameter or well.length) / 2 * 0.7

    aspirate_pos = [well.bottom((height_min + height_max)/2)]
    dispense_heights = [height_max, (height_min + height_max)/2,  height_min]
    dispense_xy_directions = [(1, 0), (0, 1), (-1, 0),  (0, -1),  (1, -1),  (1, 1), (-1, +1), (-1, -1)]

    dispense_pos = [well.bottom(h).move(Point(x=x_side*side_movement, y=y_side*side_movement))
                    for h, (x_side, y_side) in islice(zip(cycle(dispense_heights),
                                                      dispense_xy_directions), repetitions)]

    for i, (a, d) in enumerate(zip(cycle(aspirate_pos), dispense_pos)):
        if i == (repetitions - 1) and last_dispense_flow_rate is not None:
            pipette.flow_rate.dispense = last_dispense_flow_rate
        pipette.move_to(a, speed=travel_speed, publish=False)
        pipette.aspirate(volume)
        pipette.move_to(d, speed=travel_speed, publish=False)
        pipette.dispense(volume)
    pipette.move_to(well.bottom(height_max), speed=travel_speed, publish=False)


class LibraryStation(CovidseqBaseStation):
    def __init__(self,
                 ot_name="OT2",
                 tipracks20_slots: Tuple[str, ...] = ("1", "2", "3"),
                 tipracks300_slots: Tuple[str, ...] = ("4",),
                 input_plate_slot=9,
                 reagent_plate_slot=6,
                 wash_plate_slot=7,
                 work_plate_slot=5,
                 magdeck_slot=11,
                 pcr_plate_bottom_height=0.5,
                 skip_mix: bool = False,
                 mag_height=14,
                 *args, **kwargs):
        super().__init__(ot_name=ot_name, *args, **kwargs)
        self._pipette_chooser = PipetteChooser()
        self._input_plate_slot = input_plate_slot
        self._reagent_plate_slot = reagent_plate_slot
        self._wash_plate_slot = wash_plate_slot
        self._work_plate_slot = work_plate_slot
        self._magdeck_slot = magdeck_slot
        self._pcr_plate_bottom_height = pcr_plate_bottom_height
        self._skip_mix = skip_mix
        self._tipracks20_slots = tipracks20_slots
        self._tipracks300_slots = tipracks300_slots
        self._mag_height = mag_height

    @labware_loader(0, "_tipracks300")
    def load_tipracks300(self):
        self._tipracks300 = [
            self.load_labware_with_offset('opentrons_96_filtertiprack_200ul', slot, '200ul filter tiprack')
            for slot in self._tipracks300_slots]

    @labware_loader(0, "_tipracks20")
    def load_tipracks20(self):
        self._tipracks20 = [
            self.load_labware_with_offset('opentrons_96_filtertiprack_20ul', slot, '20ul filter tiprack')
            for slot in self._tipracks20_slots]

    @instrument_loader(0, '_p20')
    def load_p20(self):
        self._p20 = self._ctx.load_instrument('p20_multi_gen2', 'right', tip_racks=self._tipracks20)
        self._pipette_chooser.register(self._p20, 20)

    @instrument_loader(0, '_p300')
    def load_p300(self):
        self._p300 = self._ctx.load_instrument('p300_multi_gen2', 'left', tip_racks=self._tipracks300)
        self._pipette_chooser.register(self._p300, 200)

    @labware_loader(1, '_magdeck')
    def load_magdeck(self):
        self._magdeck = self._ctx.load_module('Magnetic Module Gen2', self._magdeck_slot)

    @labware_loader(2, '_mag_plate')
    def load_mag_plate(self):
        self._mag_plate = self._magdeck.load_labware_from_definition(get_labware_json_from_filename("customvertical_96_top_right_aligned.json"))
        self.apply_offset_to_labware(self._mag_plate)

    @labware_loader(3, '_work_plate')
    def load_work_plate(self):
        self._work_plate = self._ctx.load_labware_from_definition(
            get_labware_json_from_filename("customvertical_96_top_right_aligned.json"), self._work_plate_slot, "Vertical work plate")
        self.apply_offset_to_labware(self._work_plate)

    @labware_loader(4, '_reagent_plate')
    def load_reagent_plate(self):
        self._reagent_plate = self.load_reagent_plate_in_slot(self._reagent_plate_slot)

    @labware_loader(4, '_wash_plate')
    def load_wash_plate(self):
        self._wash_plate = self.load_wash_plate_in_slot(self._wash_plate_slot)

    @labware_loader(5, '_input_plate')
    def load_input_plate(self):
        self._input_plate = self.load_labware_with_offset("nest_96_wellplate_100ul_pcr_full_skirt",
                                                   self._input_plate_slot,
                                                   "Sample input plate")

    def _tipracks(self) -> dict:
        return {
            '_tipracks20': '_p20',
            '_tipracks300': '_p300'
        }

    def get_mix_times(self, requested_mix_times):
        return 1 if self._skip_mix else requested_mix_times

    def distribute_clean(self, recipe_name, dest_labware, pipette=None, disposal_volume=None):
        """ Transfer from the passed recipe from the reagent plate.
           :param reagent_name: the recipe name to distribute
           :param dest_labware: labware to distribute to
           :param pipette: the pipette to use. If None the pipette will be choosed based on volume to distribute
           :param disposal_volume: the volume to be kept in pipette to have an equal volume in each well.
                                   If None it is set to the half of the pipette minimum volume
               """
        recipe = self.get_recipe(recipe_name)

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(recipe.volume_final)

        if recipe.use_wash_plate:
            helper = self.wash_plate_helper
        else:
            helper = self.reagent_plate_helper

        source_wells = helper.get_first_row_available_volume(recipe_name)
        source_tip_per_row = math.ceil(pipette.channels / helper.get_rows_count(recipe_name))
        self.logger.info("Source wells are: {}".format(source_wells))
        self.logger.info("We have {} tips for each source row".format(source_tip_per_row))

        if disposal_volume is None:
            disposal_volume = pipette.min_volume / 2

        self.logger.info("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        pipette_available_volume = self._pipette_chooser.get_max_volume(pipette) - disposal_volume

        self.logger.info("Source wells are: {}".format(source_wells))

        source = MultiTubeSource(vertical_speed=self._slow_vertical_speed)
        for w, v in source_wells:
            source.append_tube_with_vol(w, v + disposal_volume)
        self.logger.info("Now source is: {}".format(source))
        
        destinations = self.get_samples_first_row_for_labware(dest_labware)
        self.logger.info("Transferring to {}".format(destinations))

        for i, (dest_well) in enumerate(destinations):
            volume = recipe.volume_final
            num_transfers = math.ceil(volume / pipette_available_volume)
            self.logger.debug("We need {} transfer with {:.1f}ul pipette".format(num_transfers, pipette_available_volume))

            dest_well_with_volume = WellWithVolume(dest_well, 0)

            if self.run_stage(self.build_stage("add {} {}/{}".format(recipe_name, i+1, len(destinations)))):
                while volume > 0:
                    self.logger.debug("Remaining volume: {:1f}".format(volume))
                    volume_to_transfer = min(volume, pipette_available_volume)
                    self.logger.debug("Transferring volume {:1f} for well {}".format(volume_to_transfer, dest_well))

                    if not pipette.has_tip:
                        self.pick_up(pipette)

                    if (pipette.current_volume - disposal_volume) < volume_to_transfer:
                        total_remaining_volume = min(pipette_available_volume,
                                                     (len(destinations)-i) * recipe.volume_final) - (pipette.current_volume - disposal_volume)
                        self.logger.debug("Volume not enough, aspirating {}ul".format(total_remaining_volume))

                        source.use_volume_only(total_remaining_volume * (source_tip_per_row - 1))
                        source.prepare_aspiration(total_remaining_volume)
                        source.aspirate(pipette)

                    dest_well_with_volume.fill(volume_to_transfer)
                    with MoveWithSpeed(pipette,
                                       from_point=dest_well.bottom(dest_well_with_volume.height + 5),
                                       to_point=dest_well.bottom(dest_well_with_volume.height),
                                       speed=self._very_slow_vertical_speed, move_close=False):
                        pipette.dispense(volume_to_transfer)
                    volume -= volume_to_transfer
                self.logger.info("Final volume in tip: {}ul".format(pipette.current_volume))
            else:
                source.use_volume_only(volume)

        if pipette.has_tip:
            self.drop(pipette)

    def distribute_dirty(self, recipe_name, dest_labware, pipette=None, mix_times=0, mix_volume=0, stage_name=None):
        recipe = self.get_recipe(recipe_name)

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(recipe.volume_final)

        if recipe.use_wash_plate:
            helper = self.wash_plate_helper
        else:
            helper = self.reagent_plate_helper

        source_wells = helper.get_first_row_available_volume(recipe_name)
        source_tip_per_row = math.ceil(pipette.channels/helper.get_rows_count(recipe_name))
        self.logger.info("Source wells are: {}".format(source_wells))
        self.logger.info("We have {} tips for each source row".format(source_tip_per_row))

        source = MultiTubeSource(vertical_speed=self._slow_vertical_speed)
        for w, v in source_wells:
            source.append_tube_with_vol(w, v)
            self.logger.info("Geometry: {} {}".format(w.width, w.length))

        self.logger.info("Now source is: {}".format(source))
        destinations = self.get_samples_first_row_for_labware(dest_labware)
        self.logger.info("Transferring to {}".format(destinations))

        pipette_available_volume = self._pipette_chooser.get_max_volume(pipette)

        for i, (dest_well) in enumerate(destinations):
            volume = recipe.volume_final
            num_transfers = math.ceil(volume / pipette_available_volume)
            self.logger.debug("We need {} transfer with {:.1f}ul pipette".format(num_transfers, pipette_available_volume))

            dest_well_with_volume = WellWithVolume(dest_well, 0)

            if self.run_stage(self.build_stage("add {} {}/{}".format(stage_name or recipe_name, i + 1, len(destinations)))):
                while volume > 0:
                    self.logger.debug("Remaining volume: {:1f}".format(volume))
                    volume_to_transfer = min(volume, pipette_available_volume)
                    self.logger.debug("Transferring volume {:1f} for well {}".format(volume_to_transfer, dest_well))

                    if pipette.has_tip:
                        self.drop(pipette)                      # Multiple transfer needed, but change tip requested

                    if not pipette.has_tip:
                        self.pick_up(pipette)

                    if pipette.current_volume < volume_to_transfer:
                        total_remaining_volume = volume - pipette.current_volume
                        self.logger.debug("Volume not enough, aspirating {}ul".format(total_remaining_volume))

                        source.use_volume_only(total_remaining_volume * (source_tip_per_row - 1))
                        source.prepare_aspiration(total_remaining_volume)
                        self.logger.info("Aspirate list: {}".format(source._aspirate_list))
                        self.logger.info("Source: {}".format(source._source_tubes_and_vol))
                        source.aspirate(pipette)

                    dest_well_with_volume.fill(volume_to_transfer)
                    pipette.dispense(volume_to_transfer, dest_well.bottom(dest_well_with_volume.height))
                    volume -= volume_to_transfer

                if mix_volume != 0 and mix_times != 0:
                    mix_well(pipette, dest_well, mix_volume, self.get_mix_times(mix_times))

                pipette.move_to(dest_well.top(), speed=self._slow_vertical_speed, publish=False)
                pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))

                self.drop(pipette)
            else:
                source.use_volume_only(volume)

    def transfer_samples(self, volume, source_labware, destination_labware, mix_times=0, mix_volume=0, stage_name="add sample"):
        sources = self.get_samples_first_row_for_labware(source_labware)
        destinations = self.get_samples_first_row_for_labware(destination_labware)
        self.transfer_dirty(sources, destinations, volume, mix_times=mix_times, mix_volume=mix_volume, stage_name=stage_name)

    def transfer_dirty(self, sources, destinations, volume, pipette=None, mix_times=0, mix_volume=0, stage_name="transfer"):
        self.logger.info("Transferring samples stage {}".format(stage_name))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(volume, consider_air_gap=True)

        num_transfers_per_sample = math.ceil(volume / self._pipette_chooser.get_max_volume(pipette))
        vol_per_transfer = volume / num_transfers_per_sample

        self.logger.info(
            "We need {} transfers of {}ul for each sample".format(num_transfers_per_sample, vol_per_transfer))

        for i, (s, d) in enumerate(zip(sources, destinations)):
            if self.run_stage(self.build_stage("{} {}/{}".format(stage_name, i + 1, len(destinations)))):
                self.pick_up(pipette)
                for _ in range(num_transfers_per_sample):
                    with MoveWithSpeed(pipette,
                                       from_point=s.bottom(self._pcr_plate_bottom_height + 2.5),
                                       to_point=s.bottom(self._pcr_plate_bottom_height),
                                       speed=self._slow_vertical_speed, move_close=False):
                        pipette.aspirate(vol_per_transfer)

                    pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))
                    pipette.dispense(self._pipette_chooser.get_air_gap(pipette), d.top())

                    pipette.dispense(vol_per_transfer, d.bottom(self._pcr_plate_bottom_height))

                    if mix_volume != 0 and mix_times != 0:
                        mix_well(pipette, d, mix_volume, self.get_mix_times(mix_times))

                    pipette.move_to(d.top(), speed=self._slow_vertical_speed, publish=False)
                    pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))

                self.drop(pipette)

    def remove_supernatant(self,
                           labware,
                           waste,
                           volume,
                           pipette=None,
                           min_steps=3,
                           last_steps=3,
                           last_steps_min_height=0.1,
                           last_transfer_volume_ratio=0.1,
                           stage_name="rem sup"):
        self.logger.info("Removing supernatant from labware {} volume {}".format(labware, volume))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(volume, consider_air_gap=True)

        available_volume = self._pipette_chooser.get_max_volume(pipette, consider_air_gap=True)

        first_phase_volume = volume * (1-last_transfer_volume_ratio)
        self.logger.info("First phase volume is: {}".format(first_phase_volume))

        first_phase_steps = max(min_steps, math.ceil(first_phase_volume/available_volume))
        self.logger.info("First phase needs {} steps".format(first_phase_steps))

        sources = self.get_samples_first_row_for_labware(labware)

        def discard_liquid(pip, source_well):
            pip.move_to(source_well.top(), speed=self._slow_vertical_speed)
            pip.air_gap(self._pipette_chooser.get_air_gap(pip))
            pip.dispense(pip.current_volume, waste.top())
            pip.air_gap(self._pipette_chooser.get_air_gap(pip))

        for i, s in enumerate(sources):
            if self.run_stage("{} {}/{}".format(self.build_stage(stage_name), i+1, len(sources))):
                remaining_volume = first_phase_volume
                source_with_volume = WellWithVolume(s, volume, headroom_height=0)

                aspirate_volume = first_phase_volume / first_phase_steps
                self.logger.info("Aspirating {} volume per time".format(aspirate_volume))

                self.pick_up(pipette)

                while remaining_volume > 0:
                    pipette.move_to(s.bottom(source_with_volume.height))

                    current_height = source_with_volume.extract_vol_and_get_height(aspirate_volume)
                    current_volume = min(aspirate_volume,
                                       available_volume - pipette.current_volume - self._pipette_chooser.get_air_gap(pipette))

                    self.logger.info("Aspirating at {:.1f} volume {:.1f}".format(current_height, current_volume))

                    pipette.move_to(s.bottom(current_height), speed=self._slow_vertical_speed)
                    pipette.aspirate(current_volume)
                    remaining_volume -= current_volume

                    if pipette.current_volume == available_volume:
                        discard_liquid(pipette, s)

                last_phase_total_volume = min(available_volume, volume * last_transfer_volume_ratio * last_steps)
                last_phase_volume_per_step = last_phase_total_volume / last_steps
                self.logger.info("Last phase volume per step: {}".format(last_phase_volume_per_step))

                if (available_volume - pipette.current_volume) < last_phase_total_volume:
                    discard_liquid(pipette, s)

                start_height = source_with_volume.height
                heights = [last_steps_min_height + (start_height-last_steps_min_height) / last_steps * i for i in range(last_steps)]

                self.logger.info("Last phase needs {} steps at heights: {}".format(last_steps, heights))
                for h in reversed(heights):
                    self.logger.info("Aspirating at {}".format(h))
                    pipette.move_to(s.bottom(h), speed=self._very_slow_vertical_speed)
                    pipette.aspirate(last_phase_volume_per_step)

                for h in heights:
                    self.logger.info("Moving to {}".format(h))
                    pipette.move_to(s.bottom(h), speed=self._very_slow_vertical_speed)

                discard_liquid(pipette, s)

                self.drop(pipette)

    def anneal_rna(self):
        if self.run_stage("load samples"):
            self.pause("Load sample plate on slot {}".format(self._input_plate_slot), home=False)
        self.robot_drop_plate("SLOT{}".format(self._work_plate_slot), "CDNA1_FULL")
        self.transfer_samples(8.5, self._input_plate, self._work_plate, mix_times=5, mix_volume=16)
        self.thermal_cycle(self._work_plate, "ANNEAL")

    def first_strand_cdna(self):
        self.robot_drop_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")
        self.distribute_dirty("FS Mix", self._work_plate, mix_times=5, mix_volume=20)
        self.robot_pick_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_EMPTY")
        self.thermal_cycle(self._work_plate, "FSS")

    def amplify_cdna(self):
        self.robot_drop_plate("SLOT{}MAG".format(self._magdeck_slot), "COV12_FULL")
        sources = self.get_samples_first_row_for_labware(self._work_plate)
        destinations_cov1 = self.get_samples_first_row_for_labware(self._mag_plate)
        destinations_cov2 = self.get_samples_first_row_COV2_for_labware(self._mag_plate)
        self.transfer_dirty(sources, destinations_cov1, volume=5, mix_times=5, mix_volume=20, stage_name="COV1")
        self.transfer_dirty(sources, destinations_cov2, volume=5, mix_times=5, mix_volume=20, stage_name="COV2")

        self.robot_trash_plate("SLOT{}".format(self._work_plate_slot), "SLOT1", "CDNA_TRASH")
        self.robot_pick_plate("SLOT{}MAG".format(self._magdeck_slot), "COV12_THERMAL")
        self.robot_drop_plate("SLOT{}".format(self._work_plate_slot), "COV12_THERMAL")
        self.thermal_cycle(self._work_plate, "PCR")

    def tagment_pcr_amplicons(self):
        self.robot_drop_plate("SLOT{}MAG".format(self._magdeck_slot), "TAG1_FULL")
        sources_cov1 = self.get_samples_first_row_for_labware(self._work_plate)
        sources_cov2 = self.get_samples_first_row_COV2_for_labware(self._work_plate)
        destinations = self.get_samples_first_row_for_labware(self._mag_plate)
        self.transfer_dirty(sources_cov1, destinations, volume=10, stage_name="COV1")
        self.transfer_dirty(sources_cov2, destinations, volume=10, mix_times=5, mix_volume=20, stage_name="COV2")

        self.robot_trash_plate("SLOT{}".format(self._work_plate_slot), "SLOT2", "COV12_TRASH")

        self.robot_pick_plate("SLOT{}MAG".format(self._magdeck_slot), "TAG1_THERMAL")
        self.robot_drop_plate("SLOT{}".format(self._work_plate_slot), "TAG1_THERMAL")

        self.thermal_cycle(self._work_plate, "TAG")

    def post_tagmentation_cleanup(self):
        self.disengage_magnets()

        self.robot_drop_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")
        self.robot_pick_plate("SLOT{}".format(self._work_plate_slot), "TAG1_CLEANUP")
        self.robot_drop_plate("SLOT{}MAG".format(self._magdeck_slot), "TAG1_CLEANUP")
        self.distribute_dirty("ST2", self._mag_plate, mix_times=10, mix_volume=20)
        self.robot_pick_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_EMPTY")

        self.engage_magnets()
        self.delay_start_count()

        self.robot_drop_plate("SLOT{}WASH".format(self._wash_plate_slot), "WASH_FULL")
        self.delay_wait_to_elapse(minutes=3)
        self.remove_supernatant(self._mag_plate, self._wash_plate.wells_by_name()['A12'], 50)
        self.disengage_magnets()

        self.distribute_dirty("TWB", self._mag_plate, mix_times=10, mix_volume=80, stage_name="TWB1")
        self.engage_magnets()
        self.delay_wait_to_elapse(minutes=3)

        self.remove_supernatant(self._mag_plate, self._wash_plate.wells_by_name()['A12'], 100, stage_name="rem TWB1")
        self.disengage_magnets()

        self.distribute_dirty("TWB", self._mag_plate, mix_times=10, mix_volume=80, stage_name="TWB2")

        # for now make plate available for user interaction now.
        self.robot_pick_plate("SLOT{}MAG".format(self._magdeck_slot), "TAG1_COMPLETED")
        self.robot_drop_plate("SLOT{}".format(self._work_plate_slot), "TAG1_COMPLETED")

    def thermal_cycle(self, labware, cycle_name):
        if self._run_stage:
            self.dual_pause("Transfer plate {} to the thermal cycler and execute cycle: {}".format(labware, cycle_name))
        else:
            self.logger.info("Skipped thermal cycle {} because no previous step run.".format(cycle_name))

    def engage_magnets(self, height=None):
        self._magdeck.engage(height or self._mag_height)

    def disengage_magnets(self):
        self._magdeck.disengage()


class LibraryManualStation(LibraryStation):
    def __init__(self,
                 tipracks20_slots: Tuple[str, ...] = ("9", "6", "3"),
                 tipracks300_slots: Tuple[str, ...] = ("2",),
                 input_plate_slot=10,
                 reagent_plate_slot=1,
                 wash_plate_slot=5,
                 work_plate_slot=4,
                 magdeck_slot=7,
                 *args, **kwargs):
        super().__init__(
            tipracks20_slots=tipracks20_slots,
            tipracks300_slots=tipracks300_slots,
            input_plate_slot=input_plate_slot,
            reagent_plate_slot=reagent_plate_slot,
            wash_plate_slot=wash_plate_slot,
            work_plate_slot=work_plate_slot,
            magdeck_slot=magdeck_slot,
            *args, **kwargs)

    @labware_loader(2, '_mag_plate')
    def load_mag_plate(self):
        self._mag_plate = self._magdeck.load_labware("nest_96_wellplate_100ul_pcr_full_skirt", "Mag plate")
        self.apply_offset_to_labware(self._mag_plate)

    @labware_loader(3, '_work_plate')
    def load_work_plate(self):
        self._work_plate = self._ctx.load_labware("nest_96_wellplate_100ul_pcr_full_skirt",
                                                  self._work_plate_slot,
                                                  "Work plate")
        self.apply_offset_to_labware(self._work_plate)


