import logging
import math

COLUMN_HEIGHT = 8

class VerticalMapper:
    def __init__(self, columns, logger=logging.getLogger(__name__)):
        self._logger = logger
        self._columns = columns
        self._available_row_length = len(self._columns)
        self._available_column_length = len(self._columns[0])
        self._row_offset = self._calc_row_offset(COLUMN_HEIGHT)
        self._logger.info("Vertical mapper column length {}; row length: {}".format(self._available_column_length,
                                                                                    self._available_row_length))
    def get_map_for_samples(self, num_samples):
        """ Get map for vertical plate.
            :param start_well: first well in left-upper corner from which start mapping.
            :raises VerticalMapperException if it is impossibile to map the samples passed.
        """
        samples_cols = math.ceil(num_samples/COLUMN_HEIGHT)
        self._logger.info("We have samples in {} columns".format(samples_cols))
        cols_offset = self._calc_column_offset(samples_cols)
        self._logger.info("Column offset: {}".format(cols_offset))
        self._logger.info("Starting from {}".format(self._columns[cols_offset:]))

        selected_wells = [w for c in self._columns[cols_offset:] for w in c[self._row_offset:self._row_offset+COLUMN_HEIGHT]]
        self._logger.info("Selected wells: {}".format(selected_wells))
        return selected_wells[:num_samples]

    def _calc_row_offset(self, column_height):
        return math.floor((self._available_column_length - column_height) / 2)

    def _calc_column_offset(self, row_length):
        return math.floor((self._available_row_length - row_length) / 2)
