from covmatic_covidseq.stations.library import LibraryStationNoHSTCCalibration

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080

metadata = {'apiLevel': '2.13'}
station = LibraryStationNoHSTCCalibration(robot_manager_host=FAKE_ROBOTMANAGER_HOST,
                                          robot_manager_port=FAKE_ROBOTMANAGER_PORT,
                                          num_samples=40)

def run(ctx):
    station.run(ctx)

