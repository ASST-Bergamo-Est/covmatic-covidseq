""" Base class that instantiate robot control """
from abc import ABC

from covmatic_stations.station import Station
from ..robot.robot import Robot


class RobotStationABC(Station, ABC):
    def __init__(self, ot_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._robot = Robot(ot_name)

    def robot_pick_plate(self, slot, plate_name):
        self._robot.pick_plate(slot, plate_name)

    def robot_drop_plate(self, slot, plate_name):
        self._robot.drop_plate(slot, plate_name)
