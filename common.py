"""
BLOCK 2 - SHARED CALCULATIONS AND RESULT CONTAINERS

Used by every method:
  * result containers the Excel writer understands (TableBlock, RowBlock, MethodResult)
  * end-tenor rule
  * leading non-descending run (anchor of the tail)
  * log curve through two points
A new method only fills a MethodResult; writer and backtest need no changes.
"""
from dataclasses import dataclass, field
import math

import numpy as np


# ----------------------------------------------------------------------------
# Result containers
# ----------------------------------------------------------------------------
@dataclass
class TableBlock:
    """Triangle: rows = accident periods, columns = development periods or tenors."""
    title: str
    corner: str                      # header of the first column, e.g. "accident \\ development"
    row_labels: list
    col_labels: list
    values: np.ndarray               # 2-D, NaN = empty cell
    number_format: str = "number"    # "number", "percent" or "percent1"
    is_input: bool = False           # input data in blue
    side_columns: list = field(default_factory=list)   # [(header, 1-D values)]


@dataclass
class PatternRow:
    label: str
    values: np.ndarray               # 1-D per tenor, NaN = empty cell
    number_format: str = "percent"
    highlight: bool = False          # yellow = final pattern


@dataclass
class RowBlock:
    """Rows per tenor (1, 2, 3, ...)."""
    title: str
    tenors: list
    rows: list                       # list of PatternRow


@dataclass
class MethodResult:
    method_code: str                 # "M1", "M2", ... (key of the output file)
    method_name: str
    aggregate: str
    pattern: np.ndarray              # final cumulative pattern, tenor 1..T
    blocks: list                     # TableBlock / RowBlock in display order


# ----------------------------------------------------------------------------
# Shared calculations
# ----------------------------------------------------------------------------
def end_tenor_rule(data, best_estimate_latest, threshold=0.0):
    """(latest accident period + 1 - oldest accident period with BE > threshold) + 2,
    in positions on the period axis."""
    open_rows = np.flatnonzero(np.nan_to_num(best_estimate_latest) > threshold)
    if len(open_rows) == 0:
        return 2
    latest = int(data.accident_position.max())
    oldest = int(data.accident_position[open_rows[0]])
    return (latest + 1 - oldest) + 2


def leading_non_descending_run(values):
    """Length of the leading run v1 <= v2 <= ... <= vs <= 1 (ties allowed; NaN stops it)."""
    length = 0
    for t, v in enumerate(values):
        if np.isnan(v) or v > 1:
            break
        if t > 0 and v < values[t - 1]:
            break
        length += 1
    return length


def log_curve_through_points(x1, y1, x2, log=math.log):
    """y = a*log(t) + c through (x1, y1) and (x2, 1). Returns (a, c)."""
    if x2 <= x1:
        return 0.0, 1.0
    a = (1.0 - y1) / (log(x2) - log(x1))
    return a, y1 - a * log(x1)


def pad_to(values, length):
    """Extend a 1-D array with empty cells (NaN) up to `length`."""
    padded = np.full(length, np.nan)
    padded[:len(values)] = values[:length]
    return padded
