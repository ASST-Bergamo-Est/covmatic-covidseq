from covmatic_covidseq.stations.library import LibraryManualStation

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080

metadata = {'apiLevel': '2.7'}
station = LibraryManualStation(robot_manager_host=FAKE_ROBOTMANAGER_HOST, robot_manager_port=FAKE_ROBOTMANAGER_PORT)

def run(ctx):
    station.run(ctx)

