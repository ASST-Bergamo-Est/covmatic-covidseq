""" Module to manage EVA robot operations with RobotManager """
import logging
import time

from .robot_api import RobotManagerHTTP, RobotManagerSimulator


class RobotException(Exception):
    pass


class Robot:
    def __init__(self,
                 robot_name: str,
                 simulate: bool = False,
                 check_wait_time: float = 0.5):
        if not robot_name.isalnum():
            raise RobotException("Robot name not aphanumeric: {}".format(robot_name))
        self._robot_name = robot_name
        self._logger = logging.getLogger(__name__)
        self._logger.info("Simulate is {}".format(simulate))
        self._check_wait_time = 0 if simulate else check_wait_time
        self._api = RobotManagerSimulator() if simulate else RobotManagerHTTP()

    def build_request(self, action: str, slot: str, plate_name: str, ):
        return {
            "action": action,
            "position": "{}-{}".format(self._robot_name, slot),
            "plate_name": plate_name
        }

    def pick_plate(self, slot: str, plate_name: str):
        self.execute_action("pick", slot, plate_name)

    def drop_plate(self, slot: str, plate_name: str):
        self.execute_action("drop", slot, plate_name)

    def execute_action(self, action, slot, plate_name):
        action_id = self._api.action_request(self.build_request(action, slot, plate_name))
        self.wait_for_action_to_finish(action_id)

    def wait_for_action_to_finish(self, action_id):
        self._logger.info("Waiting for action to finish with id: {}".format(action_id))
        while True:
            res = self._api.check_action(action_id)
            self._logger.info("Received {}".format(res))
            if res["status"] != "pending":
                break
            else:
                if self._check_wait_time:
                    time.sleep(self._check_wait_time)
