"""
METHOD 1 - PAID TO ULTIMATE

  1. ultimate and BE on the latest diagonal (ultimate = paid + rbns + ibnr)
  2. run-off ratios r(i,k) = cumulative paid / ultimate
  3. per development period: simple and BE-weighted average over the diagonals of the
     latest `payment_periods` observation periods (valuation year and the n-1 before it)
  4. anchor x0 = end of the leading non-descending run (<= 100%)
  5. end tenor N (shared rule)
  6. log10 tail through (x0, y0) and (N, 100%); if tenor 1 is already > 100%,
     least squares on t = 2..n constrained to 100% at N
  7. final pattern
"""
import math

import numpy as np

from .. import common
from ..common import MethodResult, PatternRow, RowBlock, TableBlock

CODE = "M1"
NAME = "Method 1 - paid to ultimate"


def run(data, settings):
    s = settings.method1
    n_dev = data.n_development

    # ---- 1. latest diagonal -------------------------------------------------
    best_estimate_latest = np.nan_to_num(data.latest_diagonal(data.best_estimate))
    ultimate = np.nan_to_num(data.latest_diagonal(data.paid)) + best_estimate_latest

    # ---- 2. run-off ratios (observed cell with ultimate 0 -> 0) ---------------
    safe_ultimate = np.where(ultimate != 0, ultimate, np.nan)
    ratio = np.where(np.isnan(data.paid), np.nan, np.nan_to_num(data.paid / safe_ultimate[:, None]))

    # ---- 3. averages per development period over the latest diagonals ------
    diagonal = data.accident_position[:, None] + np.arange(n_dev)[None, :]   # observation position of each cell
    in_window = np.ones_like(ratio, dtype=bool)
    if s.payment_periods:
        in_window = diagonal >= data.latest_position - s.payment_periods + 1
    simple_avg = np.full(n_dev, np.nan)
    weighted_avg = np.full(n_dev, np.nan)
    for k in range(n_dev):
        window = np.flatnonzero(~np.isnan(ratio[:, k]) & in_window[:, k])
        if len(window) == 0:
            continue
        simple_avg[k] = ratio[window, k].mean()
        weights = best_estimate_latest[window]
        if weights.sum() > 0:
            weighted_avg[k] = (weights * ratio[window, k]).sum() / weights.sum()
        else:
            weighted_avg[k] = 1.0
    n_data = int(np.flatnonzero(~np.isnan(weighted_avg)).max()) + 1   # tenors with data

    # ---- 4. anchor ----------------------------------------------------------
    x0 = common.leading_non_descending_run(weighted_avg[:n_data])

    # ---- 5. end tenor -------------------------------------------------------
    end_tenor = s.end_tenor_override or common.end_tenor_rule(data, best_estimate_latest, s.open_threshold)

    # ---- 6. constrained log10 tail ------------------------------------------
    if x0 > 0:
        a, b = common.log_curve_through_points(x0, weighted_avg[x0 - 1], end_tenor, log=math.log10)
    else:
        fit_tenors = np.arange(2, n_data + 1)
        u = np.log10(fit_tenors) - math.log10(end_tenor)
        a = float((u * (weighted_avg[1:n_data] - 1)).sum() / (u * u).sum()) if (u * u).sum() > 0 else 0.0
        b = 1 - a * math.log10(end_tenor)

    # ---- 7. final pattern ---------------------------------------------------
    n_tenors = max(n_data + 1, end_tenor)
    pattern = np.ones(n_tenors)
    for t in range(1, n_tenors + 1):
        if t <= x0:
            pattern[t - 1] = weighted_avg[t - 1]
        elif t < end_tenor and a > 0:
            pattern[t - 1] = a * math.log10(t) + b

    # ---- output blocks ------------------------------------------------------
    development = list(range(n_dev))
    blocks = [
        TableBlock("cumulative paid", "accident \\ development", data.accident_labels, development, data.paid,
                   "number", is_input=True,
                   side_columns=[("ultimate", ultimate), ("best estimate", best_estimate_latest)]),
        TableBlock("paid / ultimate", "accident \\ development", data.accident_labels, development, ratio, "percent"),
        RowBlock("run-off", list(range(1, n_tenors + 1)), [
            PatternRow("average", common.pad_to(simple_avg[:n_data], n_tenors)),
            PatternRow("weighted average", common.pad_to(weighted_avg[:n_data], n_tenors)),
            PatternRow("final pattern", pattern, highlight=True),
        ]),
    ]
    return MethodResult(CODE, NAME, data.name, pattern, blocks)
