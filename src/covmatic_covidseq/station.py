from covmatic_robotstation.robot_station import RobotStationABC, instrument_loader, labware_loader
from abc import ABC


ROBOTMANAGER_HOST = ""


class CovidseqBaseStation(RobotStationABC, ABC):
    """ Base class that has shared information about Covidseq protocol.
        Covidseq is executed by two robot:
        - REAGENT OT: prepares solutions from reagents
        - LIBRARY OT: dispenses solutions prepared to the samples.
        Between these two robot we've a reagent plate going back and forth,
        so a common class that assigns everything shared is helpful.

        Note: this is an abstract class because each OT will have its own implementation.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(robot_manager_host=ROBOTMANAGER_HOST, *args, **kwargs)
