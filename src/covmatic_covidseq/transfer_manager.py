import logging
import math
from itertools import cycle, islice
from typing import Union

from covmatic_stations.multi_tube_source import MultiTubeSource
from covmatic_stations.utils import WellWithVolume, MoveWithSpeed
from opentrons.protocol_api import Well
from opentrons.types import Point


# General use functions

def mix_well(pipette,
             well: Union[Well, WellWithVolume],
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

    if isinstance(well, WellWithVolume):
        well_with_volume = well
    else:
        well_with_volume = WellWithVolume(well, headroom_height=0)

    height_min = well_with_volume.extract_vol_and_get_height(volume)
    well_with_volume.fill(volume)
    height_max = max(well_with_volume.height, height_min + min_z_difference)

    aspirate_pos = [well_with_volume.well.bottom((height_min + height_max)/2)]
    if onto_beads:
        dispense_heights = [beads_height]
        direction = get_magnets_direction(well_with_volume.well)
        dispense_xy_directions = [(direction, 0), (direction, 1), (direction, -1)]
    else:
        dispense_heights = [height_max, (height_min + height_max)/2,  height_min]
        dispense_xy_directions = [(1, 0), (0, 1), (-1, 0),  (0, -1),  (1, -1),  (1, 1), (-1, +1), (-1, -1)]

    limited_dispense_heights = list(map(lambda x: min(x, well_with_volume.well.depth-2), dispense_heights))
    logger.info("Dispensing at height: {}".format(limited_dispense_heights))

    well_bottom_and_side_amount = [(well_with_volume.well.bottom(h), get_side_movement(well_with_volume.well, h, side_top_ratio, side_bottom_ratio)) for h in islice(cycle(limited_dispense_heights), repetitions)]
    dispense_pos_center = [w for (w, s) in well_bottom_and_side_amount]
    dispense_pos_side = [w.move(Point(x=x_side * side_amount, y=y_side * side_amount))
                         for (w, side_amount), (x_side, y_side) in zip(well_bottom_and_side_amount, cycle(dispense_xy_directions))]

    pipette.move_to(well_with_volume.well.bottom(height_max), publish=False)
    for i, (a, d_center, d_side) in enumerate(zip(cycle(aspirate_pos), dispense_pos_center, dispense_pos_side)):
        if i == (repetitions - 1) and last_dispense_flow_rate is not None:
            pipette.flow_rate.dispense = last_dispense_flow_rate
        pipette.move_to(a, speed=travel_speed, publish=False)
        pipette.aspirate(volume)
        pipette.move_to(d_center, speed=travel_speed, publish=False)
        pipette.move_to(d_side, speed=travel_speed, publish=False)
        pipette.dispense(volume)
        pipette.move_to(d_center, speed=travel_speed, publish=False)
    pipette.move_to(well_with_volume.well.bottom(height_max), speed=travel_speed, publish=False)


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


class TransferManagerException(Exception):
    pass


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
        self._side_bottom_ratio = None
        self._side_top_ratio = None
        self._beads_expected_height = None
        self._onto_beads = None
        self._source_tips_per_row = None
        self.clear_setup_mix()
        self.clear_onto_beads_values()
        self._logger.setLevel(logging.DEBUG)

    def setup_transfer(self, pipette,
                       pipette_max_volume, pipette_air_gap,
                       vertical_speed,
                       total_volume_to_transfer=None,
                       source_tips_per_row=1,
                       horizontal_speed=25.0):
        """ Set up a new group of transfers. This function must be called before the *transfer* function.
            :param pipette: the pipette that will be used for transfers;
            :param pipette_max_volume: the maximum volume the pipette can aspirate;
            :param pipette_air_gap: the air gap to use if needed;
            :param total_volume_to_transfer: the expected total amount of liquid to be transferred. It is used to
                                             calculate how much volume to aspirate;
            :param vertical_speed: the speed to use in vertical movement to avoid drops at the bottom of the tip.
            :param source_tips_per_row: how many tips are present in each row of the source; used to track liquid.
            :param onto_beads: if dispense onto beads
        """
        self.clear_onto_beads_values()
        self._pipette = pipette
        self._total_volume_to_transfer = total_volume_to_transfer
        self._pipette_max_volume = pipette_max_volume
        self._pipette_air_gap = pipette_air_gap
        self._vertical_speed = vertical_speed
        self._source_tips_per_row = source_tips_per_row
        self._horizontal_speed = horizontal_speed
        self.clear_setup_mix()
        self.clear_onto_beads_values()

    def setup_onto_beads(self,
                         onto_beads = True,
                         beads_expected_height=8,
                         side_top_ratio=1.0,
                         side_bottom_ratio=0.4):
        """
            :param beads_expected_height: the height to dispense onto beads. If None it will be calculated based on
                                          transferred liquid.
            :param side_top_ratio: the percentage of radius to reach at the top of the well; 1.0 means the well border
            :param side_bottom_ratio: the percentage of radius to reach at the bottom of the well; 0.0 means well center
        """
        self._onto_beads = onto_beads
        self._beads_expected_height = beads_expected_height
        self._side_top_ratio = side_top_ratio
        self._side_bottom_ratio = side_bottom_ratio

    def clear_onto_beads_values(self):
        self.setup_onto_beads(False)

    def setup_mix(self, mix_times=0, mix_volume=0):
        self._mix_times = mix_times
        self._mix_volume = mix_volume

    def clear_setup_mix(self):
        self.setup_mix()

    @property
    def _mix_enabled(self):
        return self._mix_volume != 0 and self._mix_times != 0

    def transfer(self, source: Union[Well, MultiTubeSource],
                 destination: Union[Well, WellWithVolume],
                 volume: float,
                 disposal_volume: float = 0,
                 change_tip: bool = False,
                 drop_tip_after: bool = False):
        self._logger.info("Starting transfer using pipette {}".format(self._pipette))
        self._logger.info("Current volume: {}ul; total volume: {}".format(volume, self._total_volume_to_transfer))
        self._logger.info("Air gap is: {}".format(self._pipette_air_gap))
        self._logger.info("Change tip is {}; drop tip after is {}".format(change_tip, drop_tip_after))

        pipette_available_volume = self._pipette_max_volume - self._pipette_air_gap - disposal_volume
        self._logger.info("Available volume: {}".format(pipette_available_volume))

        num_transfers = math.ceil(volume / pipette_available_volume)
        self._logger.debug("We need {} transfer with {:.1f}ul pipette".format(num_transfers, self._pipette_max_volume))

        dest_well_with_volume = self._get_well_with_volume(destination)

        while volume > 0:
            if change_tip and self._pipette.has_tip:
                self._drop_function(self._pipette)

            if not self._pipette.has_tip:
                self._pick_function(self._pipette)

            self._logger.debug("Remaining volume: {:1f}".format(volume))
            volume_to_transfer = min(volume, pipette_available_volume)
            self._logger.debug("Transferring volume {:1f} for well {}".format(volume_to_transfer, dest_well_with_volume.well))

            if (self._pipette.current_volume - self._pipette_air_gap - disposal_volume) < volume_to_transfer:
                if self._pipette_air_gap and self._pipette.current_volume >= self._pipette_air_gap:
                    self._pipette.dispense(self._pipette_air_gap, self._get_well(source).top())

                total_remaining_volume = min(pipette_available_volume, self._total_volume_to_transfer or volume_to_transfer) - (
                        self._pipette.current_volume - disposal_volume)
                self._logger.debug("Volume not enough, aspirating {:.1f}ul".format(total_remaining_volume))
                self._aspirate(total_remaining_volume, source)

                if self._pipette_air_gap:
                    self._pipette.air_gap(self._pipette_air_gap)

            dest_well_with_volume.fill(volume_to_transfer)
            self._logger.debug("Volume in tip before dispensing: {}ul".format(self._pipette.current_volume))
            self._logger.debug("Dispensing at {}".format(dest_well_with_volume.height))

            height = min(self._beads_expected_height, dest_well_with_volume.well.depth - 2) if self._onto_beads else dest_well_with_volume.height
            side_movement = get_side_movement(dest_well_with_volume.well, height, self._side_top_ratio, self._side_bottom_ratio) if self._onto_beads else 0

            self._logger.info("Current height: {}".format(height))
            dest_central = dest_well_with_volume.well.bottom(height)
            dest_above = dest_well_with_volume.well.bottom(height + 5)
            dest_side = dest_central.move(Point(x=side_movement))

            if self._pipette_air_gap:
                self._pipette.move_to(dest_well_with_volume.well.top(), publish=None)
                self._pipette.dispense(self._pipette_air_gap)

            with MoveWithSpeed(self._pipette,
                               from_point=dest_above,
                               to_point=dest_central,
                               speed=self._vertical_speed, move_close=False):
                self._pipette.move_to(dest_side, speed=self._horizontal_speed, publish=None)
                self._pipette.dispense(volume_to_transfer)
                self._pipette.move_to(dest_central, speed=self._horizontal_speed, publish=None)

            volume -= volume_to_transfer
            if self._total_volume_to_transfer is not None:
                self._total_volume_to_transfer -= volume_to_transfer
            self._logger.debug("Volume in tip: {}ul".format(self._pipette.current_volume))

            if volume > 0:      # we need to do another cycle
                if self._pipette_air_gap:
                    self._pipette.air_gap(self._pipette_air_gap)

        self._logger.debug("Checking for mix")
        if self._mix_enabled:
            mix_well(self._pipette, dest_well_with_volume,
                     min(self._mix_volume, self._pipette_max_volume), self._mix_times,
                     travel_speed=self._horizontal_speed, onto_beads=self._onto_beads,
                     beads_height=self._beads_expected_height, side_top_ratio=self._side_top_ratio, side_bottom_ratio=self._side_bottom_ratio)
            self._pipette.move_to(dest_well_with_volume.well.top(), speed=self._vertical_speed, publish=False)

        self._logger.debug("Checking for air gap")
        if self._pipette_air_gap:
            self._pipette.air_gap(self._pipette_air_gap)

        if drop_tip_after:
            self._drop_function(self._pipette)

    def _aspirate(self, volume, source):
        if isinstance(source, MultiTubeSource):
            self._aspirate_from_mts(volume, source)
        else:
            self._aspirate_from_source(volume, source)
        self._logger.info("Aspiration complete")

    def _aspirate_from_mts(self, volume, source: MultiTubeSource):
        self._logger.info("Aspirating from multi tube source {} {}ul".format(source, volume))
        source.use_volume_only(volume * (self._source_tips_per_row - 1))
        source.prepare_aspiration(volume)
        source.aspirate(self._pipette)

    def _aspirate_from_source(self, volume, source):
        self._logger.info("Aspirating from {} {}ul".format(source, volume))
        if isinstance(source, WellWithVolume):
            well = source.well
            aspirate_height = source.extract_vol_and_get_height(volume * self._source_tips_per_row)
        else:
            well = source
            aspirate_height = 0.5

        with MoveWithSpeed(self._pipette,
                           from_point=well.bottom(aspirate_height + 5),
                           to_point=well.bottom(aspirate_height),
                           speed=self._vertical_speed, move_close=False):
            self._pipette.aspirate(volume)

    def _dispense(self, volume: float, well: Union[Well, WellWithVolume, MultiTubeSource]):
        self._logger.info("Dispensing volume {} in {}".format(volume, well))
        well_with_volume = self._get_well_with_volume(well)
        well_with_volume.fill(volume)

        with MoveWithSpeed(self._pipette,
                           from_point=well_with_volume.well.bottom(well_with_volume.height + 5),
                           to_point=well_with_volume.well.bottom(well_with_volume.height),
                           speed=self._vertical_speed, move_close=False):
            self._pipette.dispense(volume)

    def _get_well(self, source: Union[Well, WellWithVolume, MultiTubeSource]):
        self._logger.info("GetWell source is: {}".format(type(source)))
        if isinstance(source, MultiTubeSource):
            ret = source.get_current_well()
        elif isinstance(source, WellWithVolume):
            ret = source.well
        else:
            ret = source
        return ret

    @staticmethod
    def _get_well_with_volume(well: Union[Well, WellWithVolume, MultiTubeSource]):
        if isinstance(well, MultiTubeSource):
            well_with_volume = well.get_current_well_with_volume()
        elif isinstance(well, WellWithVolume):
            well_with_volume = well
        elif isinstance(well, Well):
            well_with_volume = WellWithVolume(well, 0)
        else:
            raise TransferManagerException("Well passed is not of expected type: {} of type {}.".format(well, type(well)))
        return well_with_volume

    def mix(self, destination: Union[Well, WellWithVolume], drop_tip: bool = False):
        well_with_volume = self._get_well_with_volume(destination)

        if not self._pipette.has_tip:
            self._pick_function(self._pipette)

        mix_well(self._pipette, well_with_volume,
                 min(self._mix_volume, self._pipette_max_volume), self._mix_times,
                 travel_speed=self._horizontal_speed, onto_beads=self._onto_beads,
                 beads_height=self._beads_expected_height, side_top_ratio=self._side_top_ratio,
                 side_bottom_ratio=self._side_bottom_ratio)

        over_the_liquid_height = min(well_with_volume.well.depth - 2, well_with_volume.height + 5)
        self._pipette.move_to(well_with_volume.well.bottom(over_the_liquid_height), speed=self._vertical_speed, publish=False)

        if self._pipette_air_gap:
            self._pipette.air_gap(self._pipette_air_gap)

        if drop_tip:
            self._drop_function(self._pipette)
