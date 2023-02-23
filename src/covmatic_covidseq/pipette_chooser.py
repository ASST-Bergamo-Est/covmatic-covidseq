import logging
import bisect

from opentrons.protocol_api.instrument_context import InstrumentContext


class PipetteChooserException(Exception):
    pass


class PipetteChooser:
    def __init__(self, air_gap_fraction=0.1, logger=logging.getLogger(__name__)):
        self._pipettes = []
        self._logger = logger
        self._air_gap_fraction = air_gap_fraction

    def register(self, pipette, max_volume, air_gap_volume=None):
        """ Registration of a pipette with its parameter
            :param pipette: the pipette object to register
            :param max_volume: the maximum volume handled by the pipette
            :param air_gap_volume: the air gap to consider when choosing a pipette. If None the 10% of pipette volume is used
        """
        self._logger.info("Registering pipette {} with max volume {}".format(pipette, max_volume))
        self._logger.info("Air gap is {}".format(air_gap_volume))
        volumes = [p["max_volume"] for p in self._pipettes]
        bisect.insort(volumes, max_volume)
        self._pipettes.insert(volumes.index(max_volume), {"pipette": pipette,
                                                          "max_volume": max_volume,
                                                          "air_gap": air_gap_volume or max_volume*self._air_gap_fraction})
        self._logger.debug("Pipettes are: {}".format(self._pipettes))

    def _find_pipette(self, pipette):
        for p in self._pipettes:
            if p["pipette"] == pipette:
                return p
        raise PipetteChooserException("No pipette found for {}".format(pipette))

    def get_pipette(self, volume, consider_air_gap: bool=False) -> InstrumentContext:
        selected = self._pipettes[-1]
        for p in self._pipettes:
            if p["max_volume"] >= (volume + (p["air_gap"] if consider_air_gap else 0)):
                selected = p
                break
        self._logger.info("Selected pipette {} for volume {}".format(selected["pipette"], volume))
        return selected["pipette"]

    def get_max_volume(self, pipette, consider_air_gap: bool=False):
        p = self._find_pipette(pipette)
        return p["max_volume"] - (p["air_gap"] if consider_air_gap else 0)

    def get_air_gap(self, pipette):
        return self._find_pipette(pipette)["air_gap"]
