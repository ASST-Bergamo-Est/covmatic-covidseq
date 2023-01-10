""" Module to manage EVA robot operations with RobotManager """
import time

from .robot_api import RobotManagerApi


class RobotException(Exception):
    pass


class Robot:
    def __init__(self, robot_name: str):
        if not robot_name.isalnum():
            raise RobotException("Robot name not aphanumeric: {}".format(robot_name))
        self._robot_name = robot_name
        self._api = RobotManagerApi()

    def build_request(self, action: str, slot: str, plate_name: str):
        return {
            "action": action,
            "position": "{}-{}".format(self._robot_name, slot),
            "plate_name": plate_name
        }

    def pick_plate(self, slot: str, plate_name: str):
        action_id = self._api.action_request(self.build_request("pick", slot, plate_name))
        while True:
            res = self._api.check_action(action_id)
            print("Received {}".format(res))
            if res["status"] != "pending":
                break
            else:
                time.sleep(0.5)

    def drop_plate(self, slot: str, plate_name: str):
        self._api.action_request(self.build_request("drop", slot, plate_name))
