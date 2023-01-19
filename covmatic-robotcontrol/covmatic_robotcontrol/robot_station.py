""" Base class that instantiate robot control """
from abc import ABC

from covmatic_stations.station import Station, instrument_loader
from ..robot.robot import Robot


class RobotStationABC(Station, ABC):
    def __init__(self, ot_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ot_name = ot_name

    @instrument_loader(0, "_robot")
    def load_robot(self):
        self._robot = Robot(self._ot_name, simulate=self._ctx.is_simulating())

    def robot_pick_plate(self, slot, plate_name):
        self._robot.pick_plate(slot, plate_name)

    def robot_drop_plate(self, slot, plate_name):
        self._robot.drop_plate(slot, plate_name)


