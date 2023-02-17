from typing import Tuple
from ..utils import get_labware_json_from_filename
from ..pipette_chooser import PipetteChooser
from ..station import CovidseqBaseStation, labware_loader, instrument_loader
from covmatic_stations.multi_tube_source import MultiTubeSource

class LibraryStation(CovidseqBaseStation):
    def __init__(self,
                 ot_name="OT2",
                 tipracks20_slots: Tuple[str, ...] = ("1", "2", "3"),
                 tipracks300_slots: Tuple[str, ...] = ("4",),
                 input_plate_slot=9,
                 reagent_plate_slot=6,
                 work_plate_slot=5,
                 magdeck_slot=11,
                 *args, **kwargs):
        super().__init__(ot_name=ot_name, *args, **kwargs)
        self._pipette_chooser = PipetteChooser()
        self._input_plate_slot = input_plate_slot
        self._reagent_plate_slot = reagent_plate_slot
        self._work_plate_slot = work_plate_slot
        self._magdeck_slot = magdeck_slot
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


    # def get_wells_for_reagent(self, recipe_name):
    #     all_wells_and_vols = self._reagent_plate_helper.get_wells_with_volume(recipe_name)
    #     columns = self._reagent_plate_helper.get_columns_for_reagent(recipe_name)
    #
    #     all_wells_all_vols = list(zip(*all_wells_and_vols))
    #     wells_and_vols = []
    #     for w in [c[0] for c in columns]:
    #         wells_and_vols.append(all_wells_and_vols[all_wells_all_vols[0].index(w)])
    #
    #
    #     print(wells_and_vols)
        # first_wells_and_vols = [lambda x: wells_vols[] for f in first_wells]

    def distribute(self, recipe_name, destination, change_tip=False):
        recipe = self.get_recipe(recipe_name)
        pipette = self._pipette_chooser.get_pipette(recipe.volume_to_distribute)

        source_wells = self.reagent_plate_helper.get_first_row_dispensed_volume(recipe_name)
        self.logger.info("Source wells are: {}".format(source_wells))

        source = MultiTubeSource()
        for w, v in source_wells:
            source.append_tube_with_vol(w, v)
        self.logger.info("Now source is: {}".format(source))
        # destinations =

        # self.pick_up(pipette)
        # pipette.aspirate(recipe.volume_to_distribute, wells_vols[0][0])
        # self.drop(pipette)

    def body(self):
        # self.pause("Load sample plate on slot {}".format(self._input_plate_slot))
        # self.robot_drop_plate(6, "REAGENT")
        self.distribute("EPH3", self._work_plate)


class LibraryManualStation(LibraryStation):
    def __init__(self,
                 tipracks20_slots: Tuple[str, ...] = ("9", "6", "3"),
                 tipracks300_slots: Tuple[str, ...] = ("2",),
                 input_plate_slot=5,
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


