import math
import logging
from covmatic_stations.multi_tube_source import MultiTubeSource


class UpdatableMultiTubeSource(MultiTubeSource):
    def update_wells(self, wells_list):
        if len(wells_list) != len(self._source_tubes_and_vol):
            raise Exception("wells must have same length as original tube sources.")

        for i, source_and_vol in enumerate(self._source_tubes_and_vol):
            self.logger.info("MTS {}: updating source {} with {}".format(self._name, i, wells_list[i]))
            source_and_vol["source"] = wells_list[i]


class ReagentPlateException(Exception):
    pass


class ReagentPlateHelper:
    """ Class to handle the shared plate between multiple robots.
        :param samples_per_row: list of n. of samples in each row. Used to calculate where to dispense reagents
        :param well_volume_limit: [ul] maximum allowable volume in a well. Used to calculate where to dispense reagents
        :param logger: optional, a logger object
    """
    def __init__(self, samples_per_row, num_rows=8, num_cols=12, well_volume_limit: float = 100, logger=logging.getLogger(__name__)):
        if len(samples_per_row) != 8:
            raise ReagentPlateException("Samples per row passed {} values; expected 8".format(len(samples_per_row)))
        self._logger = logger
        self._well_volume_limit = well_volume_limit
        self._num_rows = num_rows
        self._num_cols = num_cols
        self._samples_per_row = samples_per_row
        self._all_columns = list(range(self._num_cols))
        self._logger.info("all columns are {}".format(self._all_columns))
        self._assigned_columns = []
        self._reagents = {}



    @property
    def _assigned_reagents(self):
        return [r["name"] for r in self._assigned_columns]

    @property
    def _next_free_column_index(self):
        columns = []
        for c in self._assigned_columns:
            columns += c["columns"]
        next_free_index = len(columns)

        self.check_column_index(next_free_index)
        return next_free_index

    def check_column_index(self, index):
        if index >= len(self._all_columns):
            raise ReagentPlateException("Columns not available. Columns length: {}. Requested index: {}".format(
                len(self._all_columns), index))

    def assign_reagent(self, reagent_name: str,
                       volume_with_overhead_per_sample: float,
                       volume_available_per_sample: float = None,
                       vertical_speed: float = None):
        self._logger.info("Assigning reagent {} with volume {}".format(reagent_name, volume_with_overhead_per_sample))

        if reagent_name in self._assigned_reagents:
            raise ReagentPlateException("Reagent {} already assigned.".format(reagent_name))

        if volume_available_per_sample is None:
            volume_available_per_sample = volume_with_overhead_per_sample

        self._logger.info("Labware has {} rows".format(self._num_rows))

        if self._num_rows == 1:              # 1-well reservoirs
            total_volumes = [volume_with_overhead_per_sample * sum(self._samples_per_row)]
        else:                                           # 8-well reservoirs
            total_volumes = [s * volume_with_overhead_per_sample for s in self._samples_per_row]

        self._logger.debug("Total volumes: {}".format(total_volumes))

        wells_needed = [math.ceil(t/self._well_volume_limit) for t in total_volumes]
        num_columns = max(wells_needed)
        free_column_index = self._next_free_column_index

        base_volume = max(total_volumes) / max(wells_needed)
        self._logger.debug("Base volume is: {}".format(base_volume))

        rows = []
        for v in total_volumes:
            row = []
            for j in range(num_columns):
                dispensed_volume = min(base_volume, v)
                row.append(dispensed_volume)
                v = v-dispensed_volume
            rows.append(row)

        for i, r in enumerate(rows):
            self._logger.debug("Row {}: {}".format(i, r))

        columns = self.get_columns(free_column_index, free_column_index + num_columns)
        volumes_in_columns = list(zip(*rows))


        # available_wells = [w for c in columns for w in c]
        volumes = [v for r in zip(*rows) for v in r]
        first_row_volumes = [r[0] for r in zip(*rows)]
        self._logger.info("First row volumes: {}".format(first_row_volumes))

        # self._logger.debug("Available wells: {}".format(available_wells))
        self._logger.debug("Dispensed vols: {}".format(volumes))
        dispensed_volumes = [v for v in volumes if v > 0]

        volume_fraction = volume_available_per_sample / volume_with_overhead_per_sample
        self._logger.info("Volume fraction is {}".format(volume_fraction))

        available_volumes = [v*volume_fraction for v in dispensed_volumes]
        first_row_available_volumes = [v*volume_fraction for v in first_row_volumes]

        mts_8_channel = UpdatableMultiTubeSource(reagent_name, vertical_speed=vertical_speed)
        for v in first_row_available_volumes:
            mts_8_channel.append_tube_with_vol(None, v)
        self._logger.info("MultiTubeSource has: {}".format(mts_8_channel.locations_and_vol))

        self._assigned_columns.append({
            "name": reagent_name,
            "columns": [{c: volumes_in_columns[i]} for i, c in enumerate(columns)],
            "volumes": dispensed_volumes,
            "available_volumes": available_volumes,
            "mts_8_channel": mts_8_channel
        })
        self._logger.info("Assigned: {}".format(self._assigned_columns[-1]))

    def get_columns(self, start_index, stop_index):
        """ Safe method to access columns to be assigned or already assigned.
            It will check also for boundaries.
        """
        self.check_column_index(start_index)
        self.check_column_index(stop_index)
        return self._all_columns[start_index:stop_index]

    def get_columns_for_reagent(self, reagent_name: str, labware):
        if reagent_name in self._assigned_reagents:
            return [labware.columns()[k] for column in self._assigned_columns[self._assigned_reagents.index(reagent_name)]["columns"] for k in column]
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_wells_with_volume(self, reagent_name: str, labware):
        if reagent_name in self._assigned_reagents:
            wells = [w for c in self.get_columns_for_reagent(reagent_name, labware) for w in c]
            return list(zip(wells, self._assigned_columns[self._assigned_reagents.index(reagent_name)]["volumes"]))
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_first_row_dispensed_volume(self, reagent_name: str):
        if reagent_name in self._assigned_reagents:
            data = self._assigned_columns[self._assigned_reagents.index(reagent_name)]
            first_row = [c[0] for c in data["columns"]]
            return list(filter(lambda x: x[0] in first_row, data["wells"]))
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_mts_8_channel_for_labware(self, reagent_name: str, labware) -> MultiTubeSource:
        if reagent_name in self._assigned_reagents:
            data = self._assigned_columns[self._assigned_reagents.index(reagent_name)]
            first_row_wells = []
            for column in data['columns']:
                column_index = list(column.keys())[0]
                first_row_wells.append(labware.columns()[column_index][0])
            data["mts_8_channel"].update_wells(first_row_wells)
            return data["mts_8_channel"]
        raise ReagentPlateException("Get mapping: reagent {} not found in list.".format(reagent_name))

    def get_rows_count(self):
        return self._num_rows