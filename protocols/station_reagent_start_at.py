from covmatic_covidseq.stations.reagent import ReagentStation

FAKE_ROBOTMANAGER_HOST = "fakehost"
FAKE_ROBOTMANAGER_PORT = 8080
NUM_SAMPLES = 40

metadata = {'apiLevel': '2.13'}
station = ReagentStation(robot_manager_host=FAKE_ROBOTMANAGER_HOST,
                         robot_manager_port=FAKE_ROBOTMANAGER_PORT,
                         num_samples=NUM_SAMPLES,
                         start_at="Anneal RNA Dist. EPH3 2/{}".format(NUM_SAMPLES))

def run(ctx):
    station.run(ctx)

