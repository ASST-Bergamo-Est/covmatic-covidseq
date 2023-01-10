import unittest
from unittest.mock import patch

import pytest

from ..covmatic_covidseq.robot import Robot, RobotException

OT_NAME = "OT"
WRONG_NAME = "OT 1"

SLOT_NAME = "SLOT1"
POSITION = "{}-{}".format(OT_NAME, SLOT_NAME)

PLATE_NAME = "PLATE1"

expected_pick_action = {
            "action": "pick",
            "position": POSITION,
            "plate_name": PLATE_NAME
        }

expected_drop_action = {
            "action": "drop",
            "position": POSITION,
            "plate_name": PLATE_NAME
        }

FAKE_ID_PICK = "FAKEIDPICK"
FAKE_ID_DROP = "FAKEIDDROP"

PENDING_STATUS = "pending"
FINISHED_STATUS = "finished"

CHECK_RETURN_VALUE_PENDING = {
    "status": PENDING_STATUS
}

CHECK_RETURN_VALUE_FINISHED = {
    "status": FINISHED_STATUS
}

class TestRobot(unittest.TestCase):
    def setup_mocks(self):
        self._api_patcher = patch('ot_protocol.covmatic_covidseq.robot.RobotManagerApi')
        self._sleep_patcher = patch('ot_protocol.covmatic_covidseq.robot.time.sleep')
        self._mock_api = self._api_patcher.start()
        self._mock_sleep = self._sleep_patcher.start()

    def setUp(self):
        self.setup_mocks()
        self._r = Robot(OT_NAME)

    def tearDown(self) -> None:
        self._api_patcher.stop()
        self._sleep_patcher.stop()


class TestWrongName(TestRobot):
    def setUp(self):
        self.setup_mocks()

    def test_name_not_alphanum(self):
        with self.assertRaises(RobotException):
            Robot(WRONG_NAME)


class TestPickFunction(TestRobot):
    def setUp(self):
        super().setUp()
        self._r.pick_plate(SLOT_NAME, PLATE_NAME)

    def test_request(self):
        self._mock_api().action_request.assert_called_once()

    def test_request_argument(self):
        self._mock_api().action_request.assert_called_once_with(expected_pick_action)


class TestPickFunctionWaitForComplete(TestRobot):
    def setUp(self):
        super().setUp()
        self._mock_api().action_request.side_effect = [FAKE_ID_PICK]

    def test_request_calls_check(self):
        self._r.pick_plate(SLOT_NAME, PLATE_NAME)
        self._mock_api().check_action.assert_called()

    def test_request_calls_check_with_action_id(self):
        self._r.pick_plate(SLOT_NAME, PLATE_NAME)
        self._mock_api().check_action.assert_called_with(FAKE_ID_PICK)

    def test_request_read_check_return_value(self):
        self._mock_api().check_action.side_effect = [CHECK_RETURN_VALUE_FINISHED]

        self._r.pick_plate(SLOT_NAME, PLATE_NAME)

        self._mock_api().check_action.assert_called_once_with(FAKE_ID_PICK)

    def test_request_keep_calling_while_pending(self):
        self._mock_api().check_action.side_effect = [CHECK_RETURN_VALUE_PENDING, CHECK_RETURN_VALUE_FINISHED]

        self._r.pick_plate(SLOT_NAME, PLATE_NAME)

        self._mock_api().check_action.assert_called_with(FAKE_ID_PICK)
        self.assertEqual(self._mock_api().check_action.call_count, 2)

    def test_request_uses_timed_request(self):
        self._mock_api().check_action.side_effect = [CHECK_RETURN_VALUE_PENDING, CHECK_RETURN_VALUE_FINISHED]

        self._r.pick_plate(SLOT_NAME, PLATE_NAME)

        self._mock_sleep.assert_called()

    def test_request_keep_calling_while_pending_long(self):
        self._mock_api().check_action.side_effect = [CHECK_RETURN_VALUE_PENDING for _ in range(99)] + [CHECK_RETURN_VALUE_FINISHED]

        self._r.pick_plate(SLOT_NAME, PLATE_NAME)

        self._mock_api().check_action.assert_called_with(FAKE_ID_PICK)
        self.assertEqual(self._mock_api().check_action.call_count, 100)


class TestDropFunction(TestRobot):
    def setUp(self):
        super().setUp()
        self._r.drop_plate(SLOT_NAME, PLATE_NAME)

    def test_request(self):
        self._mock_api().action_request.assert_called_once()

    def test_request_argument(self):
        self._mock_api().action_request.assert_called_once_with(expected_drop_action)

