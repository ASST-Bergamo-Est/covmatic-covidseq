from covmatic_covidseq.stations.library import LibraryStationCalibration

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080

metadata = {'apiLevel': '2.13'}
station = LibraryStationCalibration(robot_manager_host=FAKE_ROBOTMANAGER_HOST,
                                    robot_manager_port=FAKE_ROBOTMANAGER_PORT,
                                    num_samples=48, skip_thermal_cycles=True)

def run(ctx):
    station.run(ctx)

