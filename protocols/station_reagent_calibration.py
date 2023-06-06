from covmatic_covidseq.stations.reagent import ReagentStationCalibration

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080

metadata = {'apiLevel': '2.13'}
station = ReagentStationCalibration(robot_manager_host=FAKE_ROBOTMANAGER_HOST,
                                    robot_manager_port=FAKE_ROBOTMANAGER_PORT,
                                    num_samples=40)

def run(ctx):
    station.run(ctx)

