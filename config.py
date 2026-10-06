"""
Settings for the run-off pattern pipeline.

Everything a user may want to change lives here, so the calculation modules
do not contain hard-coded numbers.
"""
from dataclasses import dataclass, field


# ----------------------------------------------------------------------------
# Input file layout
# ----------------------------------------------------------------------------
INPUT_SHEET = "Sheet1"

# Column names expected in the input sheet (compared case-insensitively).
COL_AGGREGATE = "aggregate"
COL_ACCIDENT = "accident"
COL_OBSERVATION = "observation"
COL_PAID = "paid"          # cumulative paid at the observation period
COL_RBNS = "rbns"
COL_IBNR = "ibnr"
REQUIRED_COLUMNS = [COL_AGGREGATE, COL_ACCIDENT, COL_OBSERVATION, COL_PAID, COL_RBNS, COL_IBNR]


# ----------------------------------------------------------------------------
# Valuation period (calculation date)
# ----------------------------------------------------------------------------
# Label of the observation period at which the patterns are calculated, written in
# the same labelling as the input (e.g. 2023, 202304, "2023Q4").
# None = latest observation period of each aggregate.
# Data after the valuation period are NOT used for the patterns; they are only used
# in the backtest (what was actually paid afterwards).
VALUATION_PERIOD = None

# Optional per-aggregate override, e.g. {"Motor quarterly": 202304}
VALUATION_BY_AGGREGATE = {}


# ----------------------------------------------------------------------------
# Output file names
# ----------------------------------------------------------------------------
OUTPUT_METHOD_FILES = {
    "M1": "output_method1_paid_to_ultimate.xlsx",
    "M2": "output_method2_paid_to_best_estimate.xlsx",
}
OUTPUT_COMPARISON_FILE = "output_comparison.xlsx"


# ----------------------------------------------------------------------------
# Method parameters
# ----------------------------------------------------------------------------
@dataclass
class Method1Settings:
    """Paid-to-ultimate, BE-weighted average, constrained log tail."""
    payment_periods: int = 6         # diagonals used: valuation year and the n-1 before it (None = all)
    open_threshold: float = 0.0      # an accident period counts as open if BE > threshold
    end_tenor_override: int = None   # None = rule (latest AY + 1 - oldest open AY) + 2


@dataclass
class Method2Settings:
    """Paid-in-period over best estimate at the previous observation."""
    pi_1: float = 0.10               # pattern at tenor 1, set by hand
    payment_periods: int = 5         # diagonals used: valuation year and the n-1 before it (None = all)
    open_threshold: float = 0.0
    end_tenor_override: int = None


@dataclass
class Settings:
    method1: Method1Settings = field(default_factory=Method1Settings)
    method2: Method2Settings = field(default_factory=Method2Settings)
