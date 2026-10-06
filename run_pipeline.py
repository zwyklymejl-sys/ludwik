"""
Run-off pattern pipeline - entry point.

    python run_pipeline.py input.xlsx [output_folder] [--valuation 2023]

--valuation  observation period at which the patterns are calculated (same labelling as the
             input, e.g. 2023 or 202304). Default: config.VALUATION_PERIOD, None = latest period.
             Data after it are used only for the backtest.

BLOCK 1  load the input and build triangles per aggregate          (runoff_pipeline/data_loader.py)
BLOCK 2  shared calculations and result containers                  (runoff_pipeline/common.py)
BLOCK 3  methods, one module each, listed in the registry           (runoff_pipeline/methods/)
BLOCK 4  write one workbook per method and a comparison file        (runoff_pipeline/excel_writer.py)
BLOCK 5  out-of-sample backtest on data after the valuation period  (runoff_pipeline/backtest.py)
Settings (valuation, windows, pi_1, thresholds, file names)         (runoff_pipeline/config.py)
"""
import argparse
import os
import time
import warnings

from runoff_pipeline import config
from runoff_pipeline.backtest import run_backtest
from runoff_pipeline.data_loader import cut_at_valuation, load_aggregates, valuation_position
from runoff_pipeline.excel_writer import sheet_names_for, write_comparison_workbook, write_method_workbook
from runoff_pipeline.methods import METHODS


def main(input_path, output_folder=".", valuation=None):
    start = time.perf_counter()
    settings = config.Settings()
    if valuation is None:
        valuation = config.VALUATION_PERIOD
    os.makedirs(output_folder, exist_ok=True)

    # ---- BLOCK 1: data ------------------------------------------------------
    aggregates = load_aggregates(input_path)
    print(f"read {len(aggregates)} aggregate(s) from {input_path}")

    results_by_method = {method.CODE: [] for method in METHODS}
    results_by_aggregate = {}
    backtests = {}
    for full in aggregates:
        # ---- valuation: keep only what is known at the valuation period -------
        label = config.VALUATION_BY_AGGREGATE.get(full.name, valuation)
        position = valuation_position(full, label)
        if position is None:
            warnings.warn(f"[{full.name}] no data at or before valuation period {label} - aggregate skipped.")
            continue
        known = cut_at_valuation(full, position)
        valuation_label = known.period_labels[position]

        # ---- BLOCK 3: run every method on the known data -----------------------
        results = []
        for method in METHODS:
            result = method.run(known, settings)
            results.append(result)
            results_by_method[method.CODE].append(result)
        results_by_aggregate[full.name] = results

        # ---- BLOCK 5: compare with what was paid after the valuation period ------
        backtests[full.name] = run_backtest(full, known, position, results)
        future = len(backtests[full.name].period_labels)
        print(f"  {full.name}: valuation {valuation_label}, {known.n_accident} accident x "
              f"{known.n_development} development periods, {future} period(s) after valuation")

    # ---- BLOCK 4: output ------------------------------------------------------
    sheet_names = sheet_names_for(list(results_by_aggregate))
    for method in METHODS:
        path = os.path.join(output_folder, config.OUTPUT_METHOD_FILES[method.CODE])
        write_method_workbook(path, results_by_method[method.CODE], sheet_names)
        print(f"written {path}")
    path = os.path.join(output_folder, config.OUTPUT_COMPARISON_FILE)
    write_comparison_workbook(path, results_by_aggregate, backtests)
    print(f"written {path}")
    print(f"done in {time.perf_counter() - start:.2f} s")


def parse_valuation(text):
    """'2023' -> 2023 (number), anything else stays text."""
    if text is None:
        return None
    try:
        number = float(text)
        return int(number) if number.is_integer() else number
    except ValueError:
        return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run-off pattern pipeline")
    parser.add_argument("input", help="input xlsx with sheet 'Sheet1'")
    parser.add_argument("output_folder", nargs="?", default=".")
    parser.add_argument("--valuation", default=None, help="valuation period label, e.g. 2023 or 202304")
    args = parser.parse_args()
    main(args.input, args.output_folder, parse_valuation(args.valuation))
