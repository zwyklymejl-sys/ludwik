"""
BLOCK 1 - DATA LOADING

Reads the long-format input (one row per accident period x observation period)
and turns every aggregate into triangles held as numpy arrays.

`paid` is cumulative paid at the observation period; rbns and ibnr are values at
the observation period; ultimate = paid + rbns + ibnr.

Periods are never interpreted as dates. Accident and observation labels are
ordered and placed on one common period axis; development period of a cell is
    k = position(observation) - position(accident)
so years (2020), quarters (202001) or any other sortable labels work the same way.
"""
from dataclasses import dataclass
import warnings

import numpy as np
import pandas as pd

from . import config


@dataclass
class AggregateData:
    """Triangles of one aggregate, shape (accident periods, development periods), NaN = not observed."""
    name: str
    accident_labels: list          # accident periods, oldest first (as text)
    period_labels: list            # all periods on the common axis (as text)
    accident_position: np.ndarray  # position of each accident period on the period axis
    latest_position: int           # position of the latest observation period
    paid: np.ndarray               # cumulative paid
    rbns: np.ndarray
    ibnr: np.ndarray

    @property
    def n_accident(self):
        return self.paid.shape[0]

    @property
    def n_development(self):
        return self.paid.shape[1]

    @property
    def best_estimate(self):
        return self.rbns + self.ibnr

    def incremental_paid(self):
        """Paid within each development period (first column = cumulative paid of the first period)."""
        incremental = np.full_like(self.paid, np.nan)
        incremental[:, 0] = self.paid[:, 0]
        incremental[:, 1:] = self.paid[:, 1:] - self.paid[:, :-1]
        return incremental

    def latest_diagonal(self, triangle):
        """Value of every accident period at the latest observation period (NaN if missing)."""
        values = np.full(self.n_accident, np.nan)
        for i in range(self.n_accident):
            k = self.latest_position - self.accident_position[i]
            if 0 <= k < self.n_development:
                values[i] = triangle[i, k]
        return values


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _sort_key(label):
    """Numbers are sorted as numbers, anything else as text."""
    try:
        return (0, float(label), "")
    except (TypeError, ValueError):
        return (1, 0.0, str(label))


def _label_text(label):
    """Show 2020.0 as '2020' and keep text labels as they are."""
    if isinstance(label, float) and label.is_integer():
        return str(int(label))
    return str(label)


def _read_input(path):
    frame = pd.read_excel(path, sheet_name=config.INPUT_SHEET)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = [c for c in config.REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Input sheet '{config.INPUT_SHEET}' is missing columns: {missing}")

    frame = frame[config.REQUIRED_COLUMNS].copy()
    frame = frame.dropna(subset=[config.COL_AGGREGATE, config.COL_ACCIDENT, config.COL_OBSERVATION])
    amounts = [config.COL_PAID, config.COL_RBNS, config.COL_IBNR]
    if frame[amounts].isna().any().any():
        warnings.warn("Empty paid / rbns / ibnr values were read as 0.")
    frame[amounts] = frame[amounts].fillna(0.0).astype(float)
    return frame


def _build_aggregate(name, rows):
    acc_col, obs_col = config.COL_ACCIDENT, config.COL_OBSERVATION

    # 1. common period axis: ordered union of accident and observation labels
    all_labels = sorted(set(rows[acc_col]) | set(rows[obs_col]), key=_sort_key)
    position = {label: p for p, label in enumerate(all_labels)}
    accident_labels = sorted(set(rows[acc_col]), key=_sort_key)
    accident_row = {label: i for i, label in enumerate(accident_labels)}
    accident_position = np.array([position[a] for a in accident_labels])

    # 2. development index of every input row
    acc_pos = rows[acc_col].map(position).to_numpy()
    obs_pos = rows[obs_col].map(position).to_numpy()
    development = obs_pos - acc_pos
    keep = development >= 0
    if not keep.all():
        warnings.warn(f"[{name}] {int((~keep).sum())} rows with observation before accident were ignored.")

    # 3. fill the triangles (duplicate cells are added up)
    latest_position = int(obs_pos[keep].max())
    shape = (len(accident_labels), latest_position - int(accident_position.min()) + 1)
    kept = rows[keep]
    i_index = kept[acc_col].map(accident_row).to_numpy()
    k_index = development[keep]
    if pd.DataFrame({"i": i_index, "k": k_index}).duplicated().any():
        warnings.warn(f"[{name}] duplicate accident/observation rows were added up.")
    observed = np.zeros(shape, dtype=bool)
    observed[i_index, k_index] = True
    triangles = {}
    for column in (config.COL_PAID, config.COL_RBNS, config.COL_IBNR):
        triangle = np.zeros(shape)
        np.add.at(triangle, (i_index, k_index), kept[column].to_numpy())
        triangle[~observed] = np.nan
        triangles[column] = triangle

    return AggregateData(
        name=str(name),
        accident_labels=[_label_text(a) for a in accident_labels],
        period_labels=[_label_text(p) for p in all_labels],
        accident_position=accident_position,
        latest_position=latest_position,
        paid=triangles[config.COL_PAID],
        rbns=triangles[config.COL_RBNS],
        ibnr=triangles[config.COL_IBNR],
    )


# ----------------------------------------------------------------------------
# Public functions
# ----------------------------------------------------------------------------
def load_aggregates(path):
    """Read the input file; one AggregateData per aggregate, in input order."""
    frame = _read_input(path)
    aggregates = []
    for name in frame[config.COL_AGGREGATE].drop_duplicates():
        rows = frame[frame[config.COL_AGGREGATE] == name]
        aggregates.append(_build_aggregate(name, rows))
    return aggregates


def valuation_position(data, valuation_label):
    """Position of the valuation period on the period axis.

    None -> latest observation. Otherwise the latest period whose label sorts at or before
    valuation_label. Returns None if all periods of the aggregate are after it."""
    if valuation_label is None:
        return data.latest_position
    target = _sort_key(valuation_label)
    position = None
    for p, label in enumerate(data.period_labels):
        if _sort_key(label) <= target:
            position = p
    if position is None or position < int(data.accident_position.min()):
        return None
    return min(position, data.latest_position)


def cut_at_valuation(data, position):
    """Data known at the valuation period: accident periods and observations up to it."""
    keep_rows = np.flatnonzero(data.accident_position <= position)
    accident_position = data.accident_position[keep_rows]
    n_dev = position - int(accident_position.min()) + 1

    def cut(triangle):
        result = triangle[keep_rows, :n_dev].copy()
        for row, acc_pos in enumerate(accident_position):
            result[row, position - acc_pos + 1:] = np.nan     # after the valuation period
        return result

    return AggregateData(
        name=data.name,
        accident_labels=[data.accident_labels[i] for i in keep_rows],
        period_labels=data.period_labels[:position + 1],
        accident_position=accident_position,
        latest_position=position,
        paid=cut(data.paid), rbns=cut(data.rbns), ibnr=cut(data.ibnr),
    )
