from covmatic_covidseq.stations.reagent import ReagentStation
import os

# Mandatory property robot_manager_host and robot_manager_port should be retrieved from config file.
config_path = os.path.join('test', 'assets', 'example_config_file.json')

metadata = {'apiLevel': '2.13'}
station = ReagentStation(num_samples=40, config_json_filepath=config_path)


def run(ctx):
    station.run(ctx)

