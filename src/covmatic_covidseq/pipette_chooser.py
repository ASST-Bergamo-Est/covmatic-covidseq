import logging
import bisect

from opentrons.protocol_api.instrument_context import InstrumentContext


class PipetteChooserException(Exception):
    pass


class PipetteChooser:
    def __init__(self, logger=logging.getLogger(__name__)):
        self._pipettes = []
        self._logger = logger

    def register(self, pipette, max_volume):
        self._logger.info("Registering pipette {} with max volume {}".format(pipette, max_volume))
        volumes = [p["max_volume"] for p in self._pipettes]
        bisect.insort(volumes, max_volume)
        self._pipettes.insert(volumes.index(max_volume), {"pipette": pipette, "max_volume": max_volume})
        self._logger.debug("Pipettes are: {}".format(self._pipettes))

    def get_pipette(self, volume) -> InstrumentContext:
        selected = self._pipettes[-1]
        for p in self._pipettes:
            if p["max_volume"] >= volume:
                selected = p
                break
        self._logger.info("Selected pipette {} for volume {}".format(selected["pipette"], volume))
        return selected["pipette"]

    def get_max_volume(self, pipette):
        for p in self._pipettes:
            if p["pipette"] == pipette:
                return p["max_volume"]
        raise PipetteChooserException("No pipette found for {}".format(pipette))
