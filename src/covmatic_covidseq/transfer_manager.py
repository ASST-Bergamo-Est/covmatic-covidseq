import logging
import math
from typing import Union

from covmatic_stations.multi_tube_source import MultiTubeSource
from covmatic_stations.utils import WellWithVolume, MoveWithSpeed
from opentrons.protocol_api import Well


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
        """ Setup a new group of transfers. This function must be called before the *transfer* function.
            :param pipette: the pipette that will be used for transfers;
            :param pipette_max_volume: the maximum volume the pipette can aspirate;
            :param pipette_air_gap: the air gap to use if needed;
            :param total_volume_to_transfer: the expected total amount of liquid to be transferred. It is used to
                                             calculate how much volume to aspirate;
            :param vertical_speed: the speed to use in vertical movement to avoid drops at the bottom of the tip.
        """
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

