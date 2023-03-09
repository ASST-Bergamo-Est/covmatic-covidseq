from covmatic_covidseq.stations.reagent import ReagentStation

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080

metadata = {'apiLevel': '2.7'}
station = ReagentStation(robot_manager_host=FAKE_ROBOTMANAGER_HOST,
                         robot_manager_port=FAKE_ROBOTMANAGER_PORT,
                         start_at="Anneal RNA Dist. EPH3 2/96")

def run(ctx):
    station.run(ctx)

