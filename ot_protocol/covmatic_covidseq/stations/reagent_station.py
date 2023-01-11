from .base_station import RobotStationABC


class OTReagentStation(RobotStationABC):
    def __init__(self, *args, **kwargs):
        super().__init__(ot_name="OT1", *args, **kwargs)

    def _tipracks(self) -> dict:
        return {}


if __name__ == "__main__":
    OTReagentStation(num_samples=96, metadata={'apiLevel': '2.7'}).simulate()
