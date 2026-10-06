"""
METHOD 2 - PAID TO BEST ESTIMATE

  1. best estimate triangle (rbns + ibnr) and paid within each period
  2. payout ratios q(i,t) = paid in development period k / BE at the end of period k-1,
     tenor t = k + 1 (only t >= 2)
  3. keep the latest `payment_periods` payment periods (diagonals)
  4. q_t = simple (unweighted) average per tenor
  5. chain: pi_1 by hand, pi_t = pi_(t-1) + (1 - pi_(t-1)) q_t, up to x1 = last tenor with data
  6. end tenor x2 (shared rule)
  7. ln tail through (x1, pi_x1) and (x2, 100%)
"""
import math

import numpy as np

from .. import common
from ..common import MethodResult, PatternRow, RowBlock, TableBlock

CODE = "M2"
NAME = "Method 2 - paid to best estimate"


def run(data, settings):
    s = settings.method2
    n_dev = data.n_development

    # ---- 1. inputs ----------------------------------------------------------
    best_estimate = data.best_estimate
    paid_in_period = data.incremental_paid()

    # ---- 2. payout ratios ---------------------------------------------------
    opening_be = np.full_like(best_estimate, np.nan)
    opening_be[:, 1:] = best_estimate[:, :-1]
    valid = ~np.isnan(paid_in_period) & ~np.isnan(opening_be) & (opening_be != 0)
    ratio = np.where(valid, paid_in_period / np.where(valid, opening_be, 1.0), np.nan)

    # ---- 3. payment-period window --------------------------------------------
    payment_position = data.accident_position[:, None] + np.arange(n_dev)[None, :]
    in_window = valid.copy()
    if s.payment_periods:
        in_window &= payment_position >= data.latest_position - s.payment_periods + 1
    ratio_used = np.where(in_window, ratio, np.nan)

    # ---- 4. simple average per tenor (q[k] belongs to tenor k + 1) ------------
    q = np.full(n_dev, np.nan)
    for k in range(1, n_dev):
        if in_window[:, k].any():
            q[k] = np.nanmean(ratio_used[:, k])

    # ---- 5. chain from pi_1, stop at the first tenor without data ---------------
    chain = [s.pi_1]
    for k in range(1, n_dev):
        if np.isnan(q[k]):
            break
        chain.append(chain[-1] + (1 - chain[-1]) * q[k])
    x1 = len(chain)

    # ---- 6. end tenor -------------------------------------------------------
    best_estimate_latest = np.nan_to_num(data.latest_diagonal(best_estimate))
    x2 = s.end_tenor_override or common.end_tenor_rule(data, best_estimate_latest, s.open_threshold)

    # ---- 7. ln tail and final pattern ---------------------------------------
    a, c = common.log_curve_through_points(x1, chain[-1], x2, log=math.log)
    n_tenors = max(x1 + 1, x2, n_dev)
    pattern = np.ones(n_tenors)
    for t in range(1, n_tenors + 1):
        if t <= x1:
            pattern[t - 1] = chain[t - 1]
        elif t < x2:
            pattern[t - 1] = a * math.log(t) + c

    # ---- output blocks ------------------------------------------------------
    development = list(range(n_dev))
    blocks = [
        TableBlock("best estimate", "accident \\ development", data.accident_labels, development, best_estimate,
                   "number", is_input=True),
        TableBlock("paid in period", "accident \\ development", data.accident_labels, development, paid_in_period,
                   "number", is_input=True),
        TableBlock("paid / opening best estimate", "accident \\ tenor", data.accident_labels,
                   list(range(1, n_dev + 1)), ratio_used, "percent1"),
        RowBlock("run-off", list(range(1, n_tenors + 1)), [
            PatternRow("payout rate", common.pad_to(q, n_tenors), "percent1"),
            PatternRow("final pattern", pattern, highlight=True),
        ]),
    ]
    return MethodResult(CODE, NAME, data.name, pattern, blocks)
