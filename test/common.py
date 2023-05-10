import logging

from src.covmatic_covidseq.station import CovidseqBaseStation

logger = logging.getLogger("TEST")
logger.setLevel(logging.DEBUG)


class CovidseqTestStation(CovidseqBaseStation):
    """ CovibseqBaseStation concrete sample class with only abstract method and property defined"""
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