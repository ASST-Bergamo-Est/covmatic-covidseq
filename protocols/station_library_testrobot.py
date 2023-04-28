from covmatic_covidseq.stations.library import LibraryStationTestRobot

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080

metadata = {'apiLevel': '2.13'}
station = LibraryStationTestRobot(robot_manager_host=FAKE_ROBOTMANAGER_HOST,
                                  robot_manager_port=FAKE_ROBOTMANAGER_PORT,
                                  num_samples=48)
def run(ctx):
    station.run(ctx)

