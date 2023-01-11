""" API to interface with RobotManager API """
import logging
from abc import ABC, abstractmethod


class RobotManagerInterface(ABC):
    """ Common interface for the API towards RobotManager"""
    @abstractmethod
    def action_request(self, action_dict) -> str:
        pass

    @abstractmethod
    def check_action(self, action_id) -> dict:
        pass


class RobotManagerHTTP(RobotManagerInterface):
    def action_request(self, action_dict) -> str:
        # TO IMPLEMENT
        pass

    def check_action(self, action_id) -> dict:
        # TO IMPLEMENT
        pass


class RobotManagerSimulator(RobotManagerInterface):
    """ Simulation API """
    def __init__(self):
        self._check_count = 0
        self._check_before_finish = 10
        self._logger = logging.getLogger(__name__)
        self._logger.info("{} starting!".format(self.__class__.__name__))

    def action_request(self, action_dict) -> str:
        self._logger.info("Received action request: {}".format(action_dict))
        return "fakeactionid"

    def check_action(self, action_id) -> dict:
        self._logger.info("Received check request for action id: {}".format(action_id))
        status = "pending"

        self._check_count += 1
        if self._check_count == self._check_before_finish:
            self._check_count = 0
            status = "finished"

        self._logger.info("Returning status {}".format(status))
        return {"status": status}

