from covmatic_covidseq.stations.reagent import ReagentStation

metadata = {'apiLevel': '2.7'}
station = ReagentStation()

def run(ctx):
    station.run(ctx)


