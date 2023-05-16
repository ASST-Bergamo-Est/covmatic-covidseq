import logging
import math
import time
from itertools import cycle, islice
from typing import Tuple

from covmatic_stations.utils import WellWithVolume, MoveWithSpeed
from opentrons.protocol_api.labware import Well
from opentrons.types import Point

from ..pipette_chooser import PipetteChooser
from ..station import CovidseqBaseStation, labware_loader, instrument_loader


def mix_well(pipette,
             well: Well,
             volume,
             repetitions,
             last_dispense_flow_rate=None,
             min_z_difference=1.0,
             travel_speed=25.0,
             onto_beads=False,
             beads_height: float = 8,
             side_top_ratio=1.0,
             side_bottom_ratio=0.4,
             logger=logging.getLogger("mix_well")):
    """ Mix a well
        :param pipette: pipette object to use
        :param well: well to mix
        :param volume: volume to mix
        :param repetitions: number of mix (aspirate-dispense) cycles
        :param last_dispense_flow_rate: flow rate to use in the last dispense to avoid leaving liquid in tip
        :param min_z_difference: the minimum difference to have in the vertical axis
        :param travel_speed: the speed between different positions.
        :param onto_beads: if dispense directly onto beads to help resuspension.
        :param beads_height: the expected height of beads in well.
        :param side_top_ratio: float from 0 to 1, the amount of side movement in percentage of well length at the top of the well.
                               if 1.0 will touch the border of the well at the top.
        :param side_bottom_ratio: float from 0 to 1, the amount of side movement in percentage of well length at the bottom of the well.
                               if 0.0 will touch the center of the well at the bottom.
    """
    logger.info("Requested mix with pipette {} for well {}; repetitions {}, volume {}".format(pipette, well,
                                                                                              repetitions, volume))

    well_with_volume = WellWithVolume(well, headroom_height=0)
    height_min = well_with_volume.height

    well_with_volume.fill(volume)
    height_max = max(well_with_volume.height, height_min + min_z_difference)

    aspirate_pos = [well.bottom((height_min + height_max)/2)]
    if onto_beads:
        dispense_heights = [beads_height]
        direction = get_magnets_direction(well)
        dispense_xy_directions = [(direction, 0), (direction, 1), (direction, -1)]
    else:
        dispense_heights = [height_max, (height_min + height_max)/2,  height_min]
        dispense_xy_directions = [(1, 0), (0, 1), (-1, 0),  (0, -1),  (1, -1),  (1, 1), (-1, +1), (-1, -1)]

    limited_dispense_heights = list(map(lambda x: min(x, well.depth-2), dispense_heights))
    logger.info("Dispensing at height: {}".format(limited_dispense_heights))

    well_bottom_and_side_amount = [(well.bottom(h), get_side_movement(well, h, side_top_ratio, side_bottom_ratio)) for h in islice(cycle(limited_dispense_heights), repetitions)]
    dispense_pos_center = [w for (w, s) in well_bottom_and_side_amount]
    dispense_pos_side = [w.move(Point(x=x_side * side_amount, y=y_side * side_amount))
                         for (w, side_amount), (x_side, y_side) in zip(well_bottom_and_side_amount, cycle(dispense_xy_directions))]

    for i, (a, d_center, d_side) in enumerate(zip(cycle(aspirate_pos), dispense_pos_center, dispense_pos_side)):
        if i == (repetitions - 1) and last_dispense_flow_rate is not None:
            pipette.flow_rate.dispense = last_dispense_flow_rate
        pipette.move_to(a, speed=travel_speed, publish=False)
        pipette.aspirate(volume)
        pipette.move_to(d_center, speed=travel_speed, publish=False)
        pipette.move_to(d_side, speed=travel_speed, publish=False)
        pipette.dispense(volume)
        pipette.move_to(d_center, speed=travel_speed, publish=False)
    pipette.move_to(well.bottom(height_max), speed=travel_speed, publish=False)


def get_magnets_opposite_direction(well: Well):
    """ Calculates the correct horizontal direction that multiplied by a horizontal positive distance will
        keep the tip away from magnets when plate is onto magnetic module.
        (Magnets are between each couple of columns, eg. 1-2 and 3-4)
    """
    for idx, c in enumerate(well.parent.columns()):
        if well in c:
            return -1 if (idx % 2 == 0) else 1
    else:
        logging.getLogger().warning("Side direction not found for well {}".format(well))
        return 0


def get_magnets_direction(well: Well):
    """ Calculates the correct horizontal direction that multiplied by a horizontal positive distance will
        keep the tip close to magnets when plate is onto magnetic module.
        (Magnets are between each couple of columns, eg. 1-2 and 3-4)
    """
    return -get_magnets_opposite_direction(well)


def get_side_movement(well, height,
                      side_top_ratio=1.0,
                      side_bottom_ratio=0.4) -> float:
    """ Get the horizontal displacement from the center of the well incrementally:
        - at top height will be well length * side_top_ratio,
        - at bottom height will be length * side_bottom_ratio
        - at passed height it will be the linear function between top and bottom;
        :param well the well to extract the data from;
        :param height: height in which to calculate the horizontal displacement;
        :param side_top_ratio: the value to multipy with the well length to calculate the side movement in the top of the well
        :param side_bottom_ratio: the value to multipy with the well length to calculate the side movement in the bottom of the well
        :return the horizontal displacement corrisponding to the height passed. Limited always to half of the well lenght

    """
    depth = well.depth
    length = well.diameter or well.length
    side_top = side_top_ratio * length / 2
    side_bottom = side_bottom_ratio * length / 2
    ret = min(length / 2, side_bottom + (side_top - side_bottom) * height / depth)
    return ret


class PlateManager:
    def __init__(self, plate_name, protocol_context=None, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._ctx = protocol_context
        self._plate_name = plate_name
        self._current_slot = None
        self._logger.info("Plate manager initialized plate {}".format(plate_name))

    @property
    def current_plate(self):
        return self.ctx.loaded_labwares[self.current_slot]

    @property
    def current_slot(self):
        if self._current_slot is None:
            raise Exception("{} plate is not loaded.".format(self._plate_name))
        return self._current_slot

    @current_slot.setter
    def current_slot(self, slot):
        self._logger.info("Loading {} plate in slot: {}".format(self._plate_name, slot))
        self._current_slot = slot

    @property
    def ctx(self):
        if self._ctx is None:
            raise Exception("Protocol context is not set or is None. Please set ctx before using {}".format(self.__class__.__name__))
        return self._ctx

    @ctx.setter
    def ctx(self, protocol_context):
        self._ctx = protocol_context


class LibraryStation(CovidseqBaseStation):
    def __init__(self,
                 ot_name="OT2",
                 tipracks20_slots: Tuple[str, ...] = ("4", "5"),
                 tipracks300_slots: Tuple[str, ...] = ("6",),
                 input_plate_slot=1,
                 wash_plate_slot=9,
                 magdeck_slot=3,
                 heater_shaker_slot=1,
                 pcr_plate_bottom_height=0.5,
                 skip_mix: bool = False,
                 skip_thermal_cycles: bool = False,
                 mag_height=14,
                 flow_rate_json_filepath="library_flow_rates.json",
                 thermal_cycles_json_filepath="library_thermal_cycles.json",
                 beads_expected_height=10.0,
                 slow_speed=25.0,
                 *args, **kwargs):
        super().__init__(
            ot_name=ot_name,
            flow_rate_json_filepath=flow_rate_json_filepath,
            *args, **kwargs)
        self._pipette_chooser = PipetteChooser()
        self._input_plate_slot = input_plate_slot
        # self._reagent_plate_slot = reagent_plate_slot
        self._wash_plate_slot = wash_plate_slot
        # self._work_plate_slot = work_plate_slot
        self._magdeck_slot = magdeck_slot
        self._hsdeck_slot = heater_shaker_slot
        self._tc_slot = 7       # Fixed, thermocycler cannot be in another position
        self._pcr_plate_bottom_height = pcr_plate_bottom_height
        self._skip_mix = skip_mix
        self._skip_thermal_cycles = skip_thermal_cycles
        self._tipracks20_slots = tipracks20_slots
        self._tipracks300_slots = tipracks300_slots
        self._mag_height = mag_height
        self._beads_expected_height = beads_expected_height
        self._slow_speed = slow_speed
        self._reagents_mts = []
        self._reagent_plate_manager = PlateManager("reagent")
        self._sample_plate_manager = PlateManager("sample")
        self._hs_start_time = None
        self._hs_requested_seconds = None
        self._thermal_cycles = self.load_json_from_file(self.check_and_get_absolute_path(thermal_cycles_json_filepath))

    def pre_loaders_initializations(self):
        super().pre_loaders_initializations()
        self._reagent_plate_manager.ctx = self._ctx
        self._sample_plate_manager.ctx = self._ctx

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
        self._mag_plate = self._magdeck.load_labware("nest_96_wellplate_100ul_pcr_full_skirt", "Mag plate")
        self.apply_offset_to_labware(self._mag_plate)

    @labware_loader(3, '_hsdeck')
    def load_hsdeck(self):
        self._hsdeck = self._ctx.load_module('heaterShakerModuleV1', self._hsdeck_slot)

    @labware_loader(4, '_hs_plate')
    def load_hs_plate(self):
        self._hs_plate = self._hsdeck.load_labware("opentrons_96_pcr_adapter_nest_wellplate_100ul_pcr_full_skirt", "Shaker plate")
        self.apply_offset_to_labware(self._hs_plate)

    @labware_loader(4, '_tcdeck')
    def load_tcdeck(self):
        self._tcdeck = self._ctx.load_module("thermocyclerModuleV2")

    @labware_loader(5, '_tc_plate')
    def load_tc_plate(self):
        self._tc_plate = self._tcdeck.load_labware("nest_96_wellplate_100ul_pcr_full_skirt", "Thermocycler plate")
        self.apply_offset_to_labware(self._tc_plate)

    @labware_loader(5, '_wash_plate')
    def load_wash_plate(self):
        self._wash_plate = self.load_wash_plate_in_slot(self._wash_plate_slot)

    def _check_and_open_hs_if_needed(self, slot):
        if slot == self._hsdeck_slot and self._run_stage:
            self._hsdeck.open_labware_latch()

    def _check_and_close_hs_if_needed(self, slot):
        if slot == self._hsdeck_slot and self._run_stage:
            self._hsdeck.close_labware_latch()

    def _check_and_open_tc_if_needed(self, slot, for_pick_plate=False):
        if slot == self._tc_slot and self._run_stage:
            self._tcdeck.deactivate_lid()
            self._tcdeck.deactivate_block()

            if self._tcdeck.lid_position != "open":
                self._tcdeck.open_lid()

            if for_pick_plate:
                self._thermocycler_release_plate()

    def _thermocycler_release_plate(self):
        self.pause("Please press the thermocycler button for 3 seconds to release the plate.")

    def _check_slot_is_accessible(self, slot, for_pick_plate=False):
        self._check_and_open_hs_if_needed(slot)
        self._check_and_open_tc_if_needed(slot, for_pick_plate)

    def _check_slot_is_workable(self, slot):
        self._check_and_close_hs_if_needed(slot)

    def _check_slot_for_drop(self, slot):
        self._check_and_open_hs_if_needed(slot)

    def _pick_plate_with_checks(self, from_slot, plate_name: str):
        self._check_slot_is_accessible(from_slot, for_pick_plate=True)
        self.robot_pick_plate("SLOT{}".format(from_slot), plate_name)

    def _drop_plate_with_checks(self, to_slot, plate_name: str):
        self._check_slot_is_accessible(to_slot)
        self.robot_drop_plate("SLOT{}".format(to_slot), plate_name)
        self._check_slot_is_workable(to_slot)

    def _transfer_plate_with_checks(self, from_slot, to_slot, plate_name):
        self._check_slot_is_accessible(from_slot, for_pick_plate=True)
        self._check_slot_is_accessible(to_slot)
        self.robot_transfer_plate_internal("SLOT{}".format(from_slot), "SLOT{}".format(to_slot), plate_name)
        self._check_slot_is_workable(to_slot)

    def _pick_managed_plate(self, manager, plate_name):
        self._pick_plate_with_checks(manager.current_slot, plate_name)
        manager.current_slot = None

    def _drop_managed_plate(self, manager, to_slot, plate_name):
        manager.current_slot = to_slot
        self._drop_plate_with_checks(manager.current_slot, plate_name)

    def pick_reagent_plate(self, plate_name="REAGENT_EMPTY"):
        self._pick_managed_plate(self._reagent_plate_manager, plate_name)

    def drop_reagent_plate_in_slot(self, slot, plate_name="REAGENT_FULL"):
        self._drop_managed_plate(self._reagent_plate_manager, slot, plate_name)

    def pick_sample_plate(self, plate_name="SAMPLES"):
        self._pick_managed_plate(self._sample_plate_manager, plate_name)

    def drop_sample_plate_in_slot(self, slot, plate_name="SAMPLES"):
        self._drop_managed_plate(self._sample_plate_manager, slot, plate_name)

    def transfer_sample_plate_internal(self, to_slot, plate_name="SAMPLES"):
        self._transfer_plate_with_checks(self._sample_plate_manager.current_slot, to_slot, plate_name)
        self._sample_plate_manager.current_slot = to_slot

    def _trash_plate_with_checks(self, from_slot, trash_slot="SLOT1", plate_name="TRASH"):
        self._check_slot_is_accessible(from_slot, for_pick_plate=True)
        self.robot_trash_plate("SLOT{}".format(from_slot), trash_slot, plate_name)

    def shake(self, speed_rpm, seconds, blocking=True):
        if self._run_stage:
            self.logger.info("Requested shake at {} rpm for {} seconds".format(speed_rpm, seconds))
            self.home()
            self._hsdeck.close_labware_latch()
            self._hsdeck.set_and_wait_for_shake_speed(speed_rpm)

            seconds = self.get_mix_seconds(seconds)

            if blocking:
                self.delay(mins=seconds / 60, msg="Shaking for {:.1f} minutes at {} rpm".format(seconds / 60, speed_rpm),
                           home=False)
                self._hsdeck.deactivate_shaker()
            else:
                self._hs_start_time = time.monotonic()
                self._hs_requested_seconds = seconds
                self.logger.info("Shaker start time: {}".format(self._hs_start_time))
        else:
            self.logger.info("Skipping shake at {} rpm for {} seconds because no previous step run.".format(speed_rpm, seconds))

    def shake_wait_for_finish(self):
        if self._run_stage:
            if self._hs_requested_seconds is None or self._hs_start_time is None:
                raise Exception("Shake function with blocking=False must be called before waiting for fininish.")

            seconds_remaining = self._hs_requested_seconds - (time.monotonic() - self._hs_start_time)
            mins_remaining = seconds_remaining / 60

            self.delay(mins=mins_remaining,
                       msg="Completing shake for {:.1f} minutes at {} rpm".format(mins_remaining, self._hsdeck.target_speed),
                       home=False)

            self._hsdeck.deactivate_shaker()
            self._hs_requested_seconds = None
        else:
            self.logger.info("Skipping waiting for shake because no previous step run.")

    def get_thermal_cycle(self, cycle_name):
        self.logger.info("Requested thermal cycle {}".format(cycle_name))
        if cycle_name in self._thermal_cycles:
            return self._thermal_cycles[cycle_name]
        raise Exception("Thermal cycle definition not found for cycle name: {}".format(cycle_name))

    def thermal_cycle(self, cycle_name):
        if self.run_stage(self.build_stage("Thermal cycle {}".format(cycle_name))):

            cycle = self.get_thermal_cycle(cycle_name)

            if self._tcdeck.lid_position != "closed":
                self._tcdeck.close_lid()

            self.msg = "Setting lid temperature to {}".format(cycle["lid_temperature"])

            if self._skip_thermal_cycles:
                self.dual_pause("Skipping thermal cycle {}".format(cycle_name))
            else:
                self._execute_thermal_cycle(cycle)

    def _execute_thermal_cycle(self, cycle):

        self.watchdog_stop()

        self._tcdeck.set_lid_temperature(temperature=cycle["lid_temperature"])

        for step in cycle["program"]:
            if step["type"] == "step":
                self.msg = "Setting block temperature to {} for {} seconds".format(
                    step["temperature"], step["hold_time_seconds"])
                self._tcdeck.set_block_temperature(temperature=step["temperature"],
                                                   hold_time_seconds=step["hold_time_seconds"],
                                                   block_max_volume=cycle["volume"])
            elif step["type"] == "profile":
                self.msg = "Executing profile for {} cycles".format(step["repetitions"])
                self.logger.info("Profile: {}".format(step["profile"]))
                self._tcdeck.execute_profile(steps=step["profile"],
                                             repetitions=step["repetitions"],
                                             block_max_volume=cycle["volume"])
            else:
                raise Exception("Thermal cycle step value not supported: {}".format(step))

        self.msg = "Setting final block temperature to {}".format(cycle["final_temperature"])

        self._tcdeck.set_lid_temperature(temperature=cycle["final_lid_temperature"])
        self._tcdeck.set_block_temperature(temperature=cycle["final_temperature"], block_max_volume=cycle["volume"])

        self.watchdog_start()

    def get_recipe_mts(self, recipe_name):
        recipe = self.get_recipe(recipe_name)

        if recipe.use_wash_plate:
            helper = self.wash_plate_helper
            labware = self._wash_plate
        else:
            helper = self.reagent_plate_helper
            labware = self._reagent_plate_manager.current_plate

        return {
            "multi_tube_source": helper.get_mts_8_channel_for_labware(recipe_name, labware),
            "rows_count": helper.get_rows_count()
        }

    def _tipracks(self) -> dict:
        return {
            '_tipracks20': '_p20',
            '_tipracks300': '_p300'
        }

    def get_mix_times(self, requested_mix_times):
        return 1 if self._skip_mix else requested_mix_times

    def get_mix_seconds(self, requested_time):
        return 1 if self._skip_mix else requested_time

    def distribute_clean(self, recipe_name, dest_labware, pipette=None, disposal_volume=None):
        """ Transfer from the passed recipe from the reagent plate.
           :param reagent_name: the recipe name to distribute
           :param dest_labware: labware to distribute to
           :param pipette: the pipette to use. If None the pipette will be choosed based on volume to distribute
           :param disposal_volume: the volume to be kept in pipette to have an equal volume in each well.
                                   If None it is set to the half of the pipette minimum volume
               """
        recipe = self.get_recipe(recipe_name)
        reagent_mts = self.get_recipe_mts(recipe_name)

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(recipe.volume_final)

        self.apply_flow_rate(pipette)

        source = reagent_mts['multi_tube_source']
        source_tip_per_row = math.ceil(pipette.channels / reagent_mts['rows_count'])
        self.logger.info("Source is: {}".format(source))
        self.logger.debug("We have {} tips for each source row".format(source_tip_per_row))

        if disposal_volume is None:
            disposal_volume = pipette.min_volume / 2

        self.logger.info("Using pipette {} with disposal volume {}".format(pipette, disposal_volume))

        pipette_available_volume = self._pipette_chooser.get_max_volume(pipette) - disposal_volume

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

    def distribute_dirty(self, recipe_name, dest_labware,
                         pipette=None, mix_times=0, mix_volume=0, stage_name=None,
                         onto_beads=False, side_top_ratio=1.0, side_bottom_ratio=0.4):
        recipe = self.get_recipe(recipe_name)
        reagent_mts = self.get_recipe_mts(recipe_name)

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(recipe.volume_final)

        self.apply_flow_rate(pipette)

        source = reagent_mts['multi_tube_source']
        source_tip_per_row = math.ceil(pipette.channels/reagent_mts['rows_count'])
        self.logger.info("Source is: {}".format(source))
        self.logger.info("We have {} tips for each source row".format(source_tip_per_row))

        destinations = self.get_samples_first_row_for_labware(dest_labware)
        self.logger.info("Transferring to {}".format(destinations))

        pipette_available_volume = self._pipette_chooser.get_max_volume(pipette)

        mix_enabled = mix_volume != 0 and mix_times != 0

        for i, (dest_well) in enumerate(destinations):
            volume = recipe.volume_final
            num_transfers = math.ceil(volume / pipette_available_volume)
            self.logger.debug("We need {} transfer with {:.1f}ul pipette".format(num_transfers, pipette_available_volume))

            dest_well_with_volume = WellWithVolume(dest_well, 0, headroom_height=0)

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
                        source.aspirate(pipette)

                    dest_well_with_volume.fill(volume_to_transfer)
                    height = min(self._beads_expected_height, dest_well.depth - 2) if onto_beads and not mix_enabled else dest_well_with_volume.height
                    side_movement = get_side_movement(dest_well, height, side_top_ratio, side_bottom_ratio) if onto_beads else 0
                    dest_central = dest_well.bottom(height)
                    dest_side = dest_central.move(Point(x=side_movement))

                    pipette.move_to(dest_central)
                    pipette.move_to(dest_side, speed=self._slow_speed)
                    pipette.dispense(volume_to_transfer)
                    pipette.move_to(dest_central, speed=self._slow_speed)

                    volume -= volume_to_transfer

                if mix_enabled:
                    mix_well(pipette, dest_well, mix_volume, self.get_mix_times(mix_times),
                             onto_beads=onto_beads, beads_height=self._beads_expected_height,
                             side_top_ratio=side_top_ratio, side_bottom_ratio=side_bottom_ratio)

                pipette.move_to(dest_well.top(), speed=self._slow_vertical_speed, publish=False)
                pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))

                self.drop(pipette)
            else:
                source.use_volume_only(volume)

    def mix_dirty(self, locations, mix_volume, mix_times, stage_name="mix", pipette=None):
        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(mix_volume, True)
        self.logger.info("Mixing {} volume {}, times {} with pipette {}".format(stage_name, mix_volume, mix_times, pipette))

        for i, location in enumerate(locations):
            if self.run_stage(self.build_stage("{} {}/{}".format(stage_name, i+1, len(locations)))):
                self.pick_up(pipette)
                pipette.move_to(location.top())
                mix_well(pipette, location, mix_volume, mix_times)
                pipette.move_to(location.top(), speed=self._slow_vertical_speed)
                pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))
                self.drop(pipette)

    def transfer_samples(self, volume, source_labware, destination_labware, mix_times=0, mix_volume=0, stage_name="add sample"):
        sources = self.get_samples_first_row_for_labware(source_labware)
        destinations = self.get_samples_first_row_for_labware(destination_labware)
        self.transfer_dirty(sources, destinations, volume, mix_times=mix_times, mix_volume=mix_volume, stage_name=stage_name)

    def transfer_dirty(self, sources, destinations, volume, pipette=None, mix_times=0, mix_volume=0, stage_name="transfer"):
        self.logger.info("Transferring samples stage {}".format(stage_name))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(volume, consider_air_gap=True)

        self.apply_flow_rate(pipette)

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
                           volume_overhead=0.05,
                           min_steps=3,
                           deep_steps=0,
                           deep_steps_min_height=0.0,
                           deep_transfer_volume_ratio=0.1,
                           side_top_ratio=1.0,
                           side_bottom_ratio=0.4,
                           stage_name="rem sup",
                           supernatant_flow_rate="supernatant removal",
                           discard_flow_rate="supernatant discard"):
        """ Supernatant removal.
            :param volume_overhead: additional fraction of *volume* to be aspirated;
                   it has been seen that aspirating at very low speed will aspirate less than expected.
            :param deep_steps: number of steps to reach the deep_steps_min_height and back; for deep removal;
            :param deep_steps_min_height: minimum height to reach during the deep removal phase;
            :param deep_transfer_volume_ratio: the volume to reserve for the deep step phase
            :param side_top_ratio: the value to multipy with the well length to calculate the side movement in the top of the well
            :param side_bottom_ratio: the value to multipy with the well length to calculate the side movement in the bottom of the well
        """
        self.logger.info("Removing supernatant from labware {} volume {}".format(labware, volume))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(volume, consider_air_gap=True)

        available_volume = self._pipette_chooser.get_max_volume(pipette, consider_air_gap=True)

        volume = volume * (1 + volume_overhead)
        self.logger.info("Volume with overhead is {}".format(volume))

        deep_phase_volume = volume * deep_transfer_volume_ratio if deep_steps > 0 else 0
        first_phase_volume = volume - deep_phase_volume
        self.logger.info("First phase volume is: {}".format(first_phase_volume))

        first_phase_steps = max(min_steps, math.ceil(first_phase_volume/available_volume))
        self.logger.info("First phase needs {} steps".format(first_phase_steps))

        sources = self.get_samples_first_row_for_labware(labware)

        def discard_liquid(pip, source_well, last_phase=False, top_height=-5):
            """ Discard the supernatant in the waste well.
                :param pip: the pipette to use
                :param source_well: the well to aspirate from
                :param last_phase: if True the pipette will be blown out and the dispense will be done to the side of the well
                :param top_height: the waste height to be passed to 'top' function.
            """
            destination = waste.top(top_height)

            if last_phase:
                destination = destination.move(Point(x=waste.length*0.3))

            self.apply_flow_rate(pip, discard_flow_rate)

            pip.move_to(source_well.top(), speed=self._slow_vertical_speed)
            pip.air_gap(self._pipette_chooser.get_air_gap(pip))

            pip.move_to(waste.top(top_height))
            pip.dispense(pip.current_volume, destination)
            if last_phase:
                pip.blow_out()

            pip.move_to(waste.top(top_height))
            pip.air_gap(self._pipette_chooser.get_air_gap(pip))

            if not last_phase:
                pip.move_to(source_well.top())
                pip.dispense(self._pipette_chooser.get_air_gap(pip))

        for i, s in enumerate(sources):
            if self.run_stage("{} {}/{}".format(self.build_stage(stage_name), i+1, len(sources))):
                remaining_volume = first_phase_volume
                source_with_volume = WellWithVolume(s, volume, headroom_height=0)

                aspirate_volume = first_phase_volume / first_phase_steps
                self.logger.info("Aspirating {} volume per time".format(aspirate_volume))

                self.apply_flow_rate(pipette, supernatant_flow_rate)
                self.pick_up(pipette)

                side_direction = get_magnets_opposite_direction(s)

                pipette.move_to(s.top())

                while remaining_volume > 0:
                    current_height = source_with_volume.extract_vol_and_get_height(aspirate_volume)
                    current_volume = min(aspirate_volume,
                                       available_volume - pipette.current_volume - self._pipette_chooser.get_air_gap(pipette))

                    self.logger.info("Aspirating at {:.1f} volume {:.1f}".format(current_height, current_volume))
                    side_offset = side_direction * get_side_movement(s, current_height, side_top_ratio, side_bottom_ratio)
                    self.logger.info("Side movement is {}".format(side_offset))
                    pipette.move_to(s.bottom(current_height).move(Point(x=side_offset)), speed=self._very_slow_vertical_speed)
                    pipette.aspirate(current_volume)
                    remaining_volume -= current_volume

                    if pipette.current_volume == available_volume:
                        discard_liquid(pipette, s)

                if deep_steps > 0:
                    last_phase_total_volume = min(available_volume, volume * deep_transfer_volume_ratio * deep_steps)
                    last_phase_volume_per_step = last_phase_total_volume / deep_steps
                    self.logger.info("Last phase volume per step: {}".format(last_phase_volume_per_step))

                    if (available_volume - pipette.current_volume) < last_phase_total_volume:
                        discard_liquid(pipette, s)

                    start_height = source_with_volume.height

                    heights = [deep_steps_min_height + (start_height - deep_steps_min_height) / deep_steps * i for i in range(deep_steps)]
                    side_offsets = [side_direction * get_side_movement(s, h) for h in heights]
                    points = [s.bottom(h).move(Point(x=side)) for h, side in zip(heights, side_offsets)]

                    self.logger.info("Last phase needs {} steps at heights: {}".format(deep_steps, heights))
                    self.apply_flow_rate(pipette, supernatant_flow_rate, 0.5)

                    for p in reversed(points):
                        pipette.move_to(p, speed=self._very_slow_vertical_speed, publish=False)
                        pipette.aspirate(last_phase_volume_per_step)

                    for p in points:
                        pipette.move_to(p, speed=self._very_slow_vertical_speed, publish=False)

                discard_liquid(pipette, s, last_phase=True)

                self.drop(pipette)

    def anneal_rna(self):
        if self.run_stage("load input plate"):
            self._check_slot_is_accessible(self._input_plate_slot)
            self.pause("Load input plate on slot {}".format(self._input_plate_slot), home=False)

            if self._input_plate_slot == self._hsdeck_slot:
                self._transfer_plate_with_checks(self._input_plate_slot, self._magdeck_slot, "INPUT_SAMPLES")

        self.drop_sample_plate_in_slot(self._hsdeck_slot, "CDNA1_FULL")

        self.transfer_samples(8.5, self._mag_plate, self._sample_plate_manager.current_plate)

        self.shake(1000, 60, blocking=False)
        self._trash_plate_with_checks(self._magdeck_slot, plate_name="INITIAL_SAMPLES")
        self.shake_wait_for_finish()

        self.transfer_sample_plate_internal(self._tc_slot, "CDNA1_THERMAL")
        self.thermal_cycle("ANNEAL")

    def first_strand_cdna(self):
        self.transfer_sample_plate_internal(self._hsdeck_slot, "CDNA1")
        self.drop_reagent_plate_in_slot(self._magdeck_slot, "REAGENT_FULL")
        self.distribute_dirty("FS Mix", self._hs_plate)
        self.shake(1000, 60, blocking=False)
        self.pick_reagent_plate("REAGENT_EMPTY")
        self.shake_wait_for_finish()
        self.transfer_sample_plate_internal(self._tc_slot, "FSS_THERMAL")
        self.thermal_cycle("FSS")

    def amplify_cdna(self):
        self.transfer_sample_plate_internal(self._magdeck_slot, "TAG1")
        self._drop_plate_with_checks(self._hsdeck_slot, "COV12_FULL")

        self._sample_plate_manager.current_slot = self._hsdeck_slot

        sources = self.get_samples_first_row_for_labware(self._mag_plate)
        destinations_cov1 = self.get_samples_first_row_for_labware(self._sample_plate_manager.current_plate)
        destinations_cov2 = self.get_samples_first_row_COV2_for_labware(self._sample_plate_manager.current_plate)
        self.transfer_dirty(sources, destinations_cov1, volume=5, stage_name="COV1")
        self.transfer_dirty(sources, destinations_cov2, volume=5, stage_name="COV2")

        self.shake(1000, 60, blocking=False)
        self._trash_plate_with_checks(self._magdeck_slot, plate_name="CDNA1")
        self.shake_wait_for_finish()

        self.transfer_sample_plate_internal(self._tc_slot, "COV12_THERMAL")
        self.thermal_cycle("PCR")

    def tagment_pcr_amplicons(self):
        self.transfer_sample_plate_internal(self._magdeck_slot, "COV12")
        self._drop_plate_with_checks(self._hsdeck_slot, "TAG1_FULL")

        self._sample_plate_manager.current_slot = self._hsdeck_slot

        sources_cov1 = self.get_samples_first_row_for_labware(self._mag_plate)
        sources_cov2 = self.get_samples_first_row_COV2_for_labware(self._mag_plate)
        destinations = self.get_samples_first_row_for_labware(self._sample_plate_manager.current_plate)
        self.transfer_dirty(sources_cov1, destinations, volume=10, stage_name="COV1")
        self.transfer_dirty(sources_cov2, destinations, volume=10, stage_name="COV2")

        self.shake(1000, 60, blocking=False)
        self._trash_plate_with_checks(self._magdeck_slot, plate_name="COV12")

        self.shake_wait_for_finish()
        self.transfer_sample_plate_internal(self._tc_slot, "TAG1")

        self.thermal_cycle("TAG")

    def post_tagmentation_cleanup(self):
        self.drop_reagent_plate_in_slot(self._magdeck_slot)
        self.transfer_sample_plate_internal(self._hsdeck_slot, "TAG1_CLEANUP")

        self.distribute_dirty("ST2", self._hs_plate)
        self.shake(1000, 60, blocking=False)

        self.pick_reagent_plate()
        self.shake_wait_for_finish()

        self.delay(mins=5)

        self.transfer_sample_plate_internal(self._magdeck_slot, "TAG1_CLEANUP")

        self.engage_magnets()

        self.delay_start_count()
        self._drop_plate_with_checks(self._wash_plate_slot, "WASH_FULL")
        self.delay_wait_to_elapse(minutes=3)

        self.remove_supernatant(self._mag_plate, self._wash_plate.wells_by_name()['A11'], 60)
        self.disengage_magnets()

        self.load_flow_rate()
        self.distribute_dirty("TWB", self._mag_plate, stage_name="TWB1")

        self.transfer_sample_plate_internal(self._hsdeck_slot)
        self.shake(1000, 60)

        self.transfer_sample_plate_internal(self._magdeck_slot)
        self.engage_magnets()
        self.delay(mins=3)

        self.remove_supernatant(self._mag_plate, self._wash_plate.wells_by_name()['A11'], 100, stage_name="rem TWB1")
        self.disengage_magnets()

        self.load_flow_rate()
        self.distribute_dirty("TWB", self._mag_plate, stage_name="TWB2")

        self.transfer_sample_plate_internal(self._hsdeck_slot)
        self.shake(1000, 60)

        self.transfer_sample_plate_internal(self._magdeck_slot)
        self.engage_magnets()
        self.delay(mins=3)

    def amplify_tagmented_amplicons(self):
        pass

    def engage_magnets(self, height=None):
        self._magdeck.engage(height_from_base=height or self._mag_height)

    def disengage_magnets(self):
        self._magdeck.disengage()


class LibraryStationTestRobot(LibraryStation):
    """ Class for test the robot movement inside the Library OT2 """
    def __init__(self, num_test_repetitions=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._num_test_repetitions = num_test_repetitions

    def _thermocycler_release_plate(self):
        pass

    def body(self):
        self._sample_plate_manager.current_slot = self._magdeck_slot
        for i in range(self._num_test_repetitions):
            self.logger.info("Test {}/{}".format(i+1, self._num_test_repetitions+1))
            self.transfer_sample_plate_internal(self._hsdeck_slot)
            self.transfer_sample_plate_internal(self._magdeck_slot)
            self.transfer_sample_plate_internal(self._tc_slot)
            self._transfer_plate_with_checks(self._wash_plate_slot, self._wash_plate_slot, "Wash plate")



