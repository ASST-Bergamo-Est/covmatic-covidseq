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
             travel_speed=25.0):
    """ Mix a well
        :param pipette: pipette object to use
        :param well: well to mix
        :param volume: volume to mix
        :param repetitions: number of mix (aspirate-dispense) cycles
        :param last_dispense_flow_rate: flow rate to use in the last dispense to avoid leaving liquid in tip
        :param min_z_difference: the minimum difference to have in the vertical axis
        :param travel_speed: the speed between different positions.
    """
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


class LibraryStation(CovidseqBaseStation):
    def __init__(self,
                 ot_name="OT2",
                 tipracks20_slots: Tuple[str, ...] = ("1", "2", "3"),
                 tipracks300_slots: Tuple[str, ...] = ("4",),
                 input_plate_slot=9,
                 reagent_plate_slot=6,
                 work_plate_slot=5,
                 magdeck_slot=11,
                 pcr_plate_bottom_height=0.5,
                 *args, **kwargs):
        super().__init__(ot_name=ot_name, *args, **kwargs)
        self._pipette_chooser = PipetteChooser()
        self._input_plate_slot = input_plate_slot
        self._reagent_plate_slot = reagent_plate_slot
        self._work_plate_slot = work_plate_slot
        self._magdeck_slot = magdeck_slot
        self._pcr_plate_bottom_height = pcr_plate_bottom_height
        self._tipracks20_slots = tipracks20_slots
        self._tipracks300_slots = tipracks300_slots

    @labware_loader(0, "_tipracks300")
    def load_tipracks300(self):
        self._tipracks300 = [
            self._ctx.load_labware('opentrons_96_filtertiprack_200ul', slot, '200ul filter tiprack')
            for slot in self._tipracks300_slots]

    @labware_loader(0, "_tipracks20")
    def load_tipracks20(self):
        self._tipracks20 = [
            self._ctx.load_labware('opentrons_96_filtertiprack_20ul', slot, '20ul filter tiprack')
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

    @labware_loader(3, '_work_plate')
    def load_work_plate(self):
        self._work_plate = self._ctx.load_labware_from_definition(
            get_labware_json_from_filename("customvertical_96_top_right_aligned.json"), self._work_plate_slot, "Vertical work plate")

    @labware_loader(4, '_reagent_plate')
    def load_reagent_plate(self):
        self._reagent_plate = self.load_reagents_plate(self._reagent_plate_slot)

    @labware_loader(5, '_input_plate')
    def load_input_plate(self):
        self._input_plate = self._ctx.load_labware("nest_96_wellplate_100ul_pcr_full_skirt",
                                                   self._input_plate_slot,
                                                   "Sample input plate")

    def samples_first_row_for_labware(self, labware):
        return [c[0] for c in labware.columns()][:self.num_cols]

    def _tipracks(self) -> dict:
        return {
            '_tipracks20': '_p20',
            '_tipracks300': '_p300'
        }

    def distribute(self, recipe_name, dest_labware, pipette=None, change_tip=False):
        recipe = self.get_recipe(recipe_name)
        pipette = self._pipette_chooser.get_pipette(recipe.volume_to_distribute)

        source_wells = self.reagent_plate_helper.get_first_row_available_volume(recipe_name)
        self.logger.info("Source wells are: {}".format(source_wells))

        source = MultiTubeSource(vertical_speed=self._slow_vertical_speed)
        for w, v in source_wells:
            source.append_tube_with_vol(w, v)
        self.logger.info("Now source is: {}".format(source))
        destinations = self.samples_first_row_for_labware(dest_labware)
        self.logger.info("Transferring to {}".format(destinations))

        if pipette is None:
            pipette = self._pipette_chooser.get_pipette(recipe.volume_final)

        self.pick_up(pipette)

        for i, (dest_well) in enumerate(destinations):
            volume = recipe.volume_final
            num_transfers = math.ceil(volume / self._pipette_chooser.get_max_volume(pipette))
            self.logger.debug("We need {} transfer with {:.1f}ul pipette".format(num_transfers,
                                                                                 self._pipette_chooser.get_max_volume(
                                                                                     pipette)))

            dest_well_with_volume = WellWithVolume(dest_well, 0)

            while volume > 0:
                self.logger.debug("Remaining volume: {:1f}".format(volume))
                volume_to_transfer = min(volume, self._pipette_chooser.get_max_volume(pipette))
                self.logger.debug("Transferring volume {:1f} for well {}".format(volume_to_transfer, dest_well))
                if pipette.current_volume < volume_to_transfer:
                    total_remaining_volume = min(self._pipette_chooser.get_max_volume(pipette),
                                                 (len(destinations)-i) * recipe.volume_final) - pipette.current_volume
                    self.logger.debug("Volume not enough, aspirating {}ul".format(total_remaining_volume))

                    source.prepare_aspiration(total_remaining_volume)
                    source.aspirate(pipette)

                dest_well_with_volume.fill(volume_to_transfer)
                with MoveWithSpeed(pipette,
                                   from_point=dest_well.bottom(dest_well_with_volume.height + 5),
                                   to_point=dest_well.bottom(dest_well_with_volume.height),
                                   speed=self._very_slow_vertical_speed, move_close=False):
                    pipette.dispense(volume_to_transfer)
                volume -= volume_to_transfer

        self.drop(pipette)

    def transfer_samples(self, volume, source_labware, destination_labware, mix_times=0, mix_volume=0):
        sources = self.samples_first_row_for_labware(source_labware)
        destinations = self.samples_first_row_for_labware(destination_labware)

        pipette = self._pipette_chooser.get_pipette(volume, consider_air_gap=True)

        num_transfers_per_sample = math.ceil(volume/self._pipette_chooser.get_max_volume(pipette))
        vol_per_transfer = volume/num_transfers_per_sample

        self.logger.info("We need {} transfers of {}ul for each sample".format(num_transfers_per_sample, vol_per_transfer))

        for s, d in zip(sources, destinations):
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
                    mix_well(pipette, d, mix_volume, mix_times)

                pipette.move_to(d.top(), speed=self._slow_vertical_speed, publish=False)
                pipette.air_gap(self._pipette_chooser.get_air_gap(pipette))

            self.drop(pipette)

    def anneal_rna(self):
        self.robot_drop_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")
        self.distribute("EPH3", self._work_plate)
        self.robot_pick_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_EMPTY")
        self.transfer_samples(8.5, self._input_plate, self._work_plate, mix_times=10, mix_volume=16)
        self.thermal_cycle(self._work_plate, "ANNEAL")

    def first_strand_cdna(self):
        self.robot_drop_plate("SLOT{}".format(self._reagent_plate_slot), "REAGENT_FULL")
        self.distribute("FS Mix", self._work_plate, change_tip=True)

    def thermal_cycle(self, labware, cycle_name):
        self.dual_pause("Transfer plate {} to the thermal cycler and execute cycle: {}".format(labware, cycle_name))

    def body(self):
        self.pause("Load sample plate on slot {}".format(self._input_plate_slot))
        self.anneal_rna()
        self.first_strand_cdna()


class LibraryManualStation(LibraryStation):
    def __init__(self,
                 tipracks20_slots: Tuple[str, ...] = ("9", "6", "3"),
                 tipracks300_slots: Tuple[str, ...] = ("2",),
                 input_plate_slot=4,
                 reagent_plate_slot=1,
                 work_plate_slot=7,
                 magdeck_slot=10,
                 *args, **kwargs):
        super().__init__(
            tipracks20_slots=tipracks20_slots,
            tipracks300_slots=tipracks300_slots,
            input_plate_slot=input_plate_slot,
            reagent_plate_slot=reagent_plate_slot,
            work_plate_slot=work_plate_slot,
            magdeck_slot=magdeck_slot,
            *args, **kwargs)

    @labware_loader(2, '_mag_plate')
    def load_mag_plate(self):
        self._mag_plate = self._magdeck.load_labware("nest_96_wellplate_100ul_pcr_full_skirt", "Mag plate")

    @labware_loader(3, '_work_plate')
    def load_work_plate(self):
        self._work_plate = self._ctx.load_labware("nest_96_wellplate_100ul_pcr_full_skirt",
                                                  self._work_plate_slot,
                                                  "Work plate")


