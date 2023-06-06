import logging

from src.covmatic_covidseq.station import CovidseqBaseStation

logger = logging.getLogger("TEST")
logger.setLevel(logging.DEBUG)

NUM_SAMPLES = 40


class CovidseqTestStation(CovidseqBaseStation):
    """ CovibseqBaseStation concrete sample class with only abstract method and property defined"""

    def __init__(self, num_samples=NUM_SAMPLES, *args, **kwargs):
        super().__init__(num_samples=num_samples, *args, **kwargs)

    def _tipracks(self):
        pass

    def anneal_rna(self):
        pass

    def first_strand_cdna(self):
        pass

    def amplify_cdna(self):
        pass

    def tagment_pcr_amplicons(self):
        pass

    def post_tagmentation_cleanup(self):
        pass

    def amplify_tagmented_amplicons(self):
        pass