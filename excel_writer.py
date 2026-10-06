"""
BLOCK 4 - EXCEL OUTPUT

Values only (no formulas): blue = input data, yellow row = final pattern.

  write_method_workbook      one file per method, one sheet per aggregate
  write_comparison_workbook  Patterns, Backtest by tenor, Backtest by period
"""
import re

import numpy as np
import xlsxwriter

from .common import RowBlock, TableBlock

MAX_SHEET_NAME = 31
NUMBER_FORMATS = {
    "number": "#,##0",
    "percent": "0.00%",
    "percent1": "0.0%",
    "integer": "0",
    "difference_percent": "0.00%;[Red]-0.00%",
    "difference_number": "#,##0;[Red]-#,##0",
}


# ----------------------------------------------------------------------------
# Formats and small helpers
# ----------------------------------------------------------------------------
class Formats:
    """All cell formats of one workbook, created once."""

    def __init__(self, book):
        base = {"font_name": "Arial", "font_size": 10}
        self.bold = book.add_format({**base, "bold": True})
        self.header = book.add_format({**base, "bold": True, "bottom": 1, "align": "center"})
        self.text = book.add_format(base)
        self.highlight_label = book.add_format({**base, "bold": True, "bg_color": "#FFFF00"})
        self.value = {}
        for kind, code in NUMBER_FORMATS.items():
            self.value[(kind, "calc")] = book.add_format({**base, "num_format": code})
            self.value[(kind, "input")] = book.add_format({**base, "num_format": code, "font_color": "#0000FF"})
            self.value[(kind, "highlight")] = book.add_format({**base, "num_format": code, "bg_color": "#FFFF00"})

    def cell(self, kind, style="calc"):
        return self.value[(kind, style)]


def write_value(sheet, row, col, value, fmt):
    """Write a number, a text or nothing (for NaN / None)."""
    if value is None:
        return
    if isinstance(value, str):
        sheet.write_string(row, col, value, fmt)
        return
    value = float(value)
    if not np.isnan(value):
        sheet.write_number(row, col, value, fmt)


def write_row(sheet, row, labels, values, first_col, fmt, label_fmt):
    """Text labels in the first columns, then one value per column."""
    for j, label in enumerate(labels):
        sheet.write_string(row, j, str(label), label_fmt)
    for j, v in enumerate(values):
        write_value(sheet, row, first_col + j, v, fmt)


def sheet_names_for(aggregates):
    """Excel-safe, unique sheet names (max 31 characters) for a list of aggregate names."""
    names, used = {}, set()
    for aggregate in aggregates:
        clean = re.sub(r"[\[\]\:\*\?\/\\]", "_", str(aggregate)).strip("'").strip() or "aggregate"
        name = clean[:MAX_SHEET_NAME]
        counter = 2
        while name.lower() in used:
            suffix = f"~{counter}"
            name = clean[:MAX_SHEET_NAME - len(suffix)] + suffix
            counter += 1
        used.add(name.lower())
        names[aggregate] = name
    return names


# ----------------------------------------------------------------------------
# Method workbooks
# ----------------------------------------------------------------------------
def _write_table(sheet, row, block, f):
    sheet.write_string(row, 0, block.title, f.bold)
    row += 1
    sheet.write_string(row, 0, block.corner, f.header)
    for j, label in enumerate(block.col_labels):
        sheet.write_number(row, 1 + j, label, f.header)
    first_side_col = 1 + len(block.col_labels)
    for s, (header, _) in enumerate(block.side_columns):
        sheet.write_string(row, first_side_col + s, header, f.header)
    style = "input" if block.is_input else "calc"
    for i, label in enumerate(block.row_labels):
        r = row + 1 + i
        write_row(sheet, r, [label], block.values[i], 1, f.cell(block.number_format, style), f.bold)
        for s, (_, values) in enumerate(block.side_columns):
            write_value(sheet, r, first_side_col + s, values[i], f.cell("number", style))
    return row + len(block.row_labels) + 3


def _write_rows(sheet, row, block, f):
    sheet.write_string(row, 0, block.title, f.bold)
    row += 1
    sheet.write_string(row, 0, "tenor", f.header)
    for j, t in enumerate(block.tenors):
        sheet.write_number(row, 1 + j, t, f.header)
    for pattern_row in block.rows:
        row += 1
        style = "highlight" if pattern_row.highlight else "calc"
        label_fmt = f.highlight_label if pattern_row.highlight else f.text
        write_row(sheet, row, [pattern_row.label], pattern_row.values, 1,
                  f.cell(pattern_row.number_format, style), label_fmt)
    return row + 3


def write_method_workbook(path, results, sheet_names):
    """results: MethodResult of ONE method, one per aggregate."""
    book = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
    f = Formats(book)
    for result in results:
        sheet = book.add_worksheet(sheet_names[result.aggregate])
        row, widest = 0, 0
        for block in result.blocks:
            if isinstance(block, TableBlock):
                row = _write_table(sheet, row, block, f)
                widest = max(widest, len(block.col_labels) + len(block.side_columns))
            elif isinstance(block, RowBlock):
                row = _write_rows(sheet, row, block, f)
                widest = max(widest, len(block.tenors))
        sheet.set_column(0, 0, 24)
        sheet.set_column(1, widest + 1, 11)
    book.close()


# ----------------------------------------------------------------------------
# Comparison workbook
# ----------------------------------------------------------------------------
def _header(sheet, labels, n_columns, column_names, f):
    for j, label in enumerate(labels):
        sheet.write_string(0, j, label, f.header)
    for j, name in enumerate(column_names[:n_columns]):
        write_value(sheet, 0, len(labels) + j, name, f.header)


def _widths(sheet, n_columns, width):
    sheet.set_column(0, 0, 40)
    sheet.set_column(1, 1, 11)
    sheet.set_column(2, 2, 40)
    sheet.set_column(3, n_columns + 3, width)
    sheet.freeze_panes(1, 3)


def write_comparison_workbook(path, results_by_aggregate, backtests):
    """results_by_aggregate: {aggregate: [MethodResult]}, backtests: {aggregate: Backtest}"""
    book = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
    f = Formats(book)
    blue = book.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#0000FF"})
    blue_percent = book.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#0000FF",
                                    "num_format": "0.00%"})
    blue_number = book.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#0000FF",
                                   "num_format": "#,##0"})

    n_tenors = 1
    for aggregate, results in results_by_aggregate.items():
        for result in results:
            n_tenors = max(n_tenors, len(result.pattern))
        n_tenors = max(n_tenors, len(backtests[aggregate].tenors))
    tenor_names = list(range(1, n_tenors + 1))
    labels = ["aggregate", "valuation"]

    # ---- Patterns ------------------------------------------------------------
    sheet = book.add_worksheet("Patterns")
    _header(sheet, labels + ["method"], n_tenors, tenor_names, f)
    row = 1
    for aggregate, results in results_by_aggregate.items():
        valuation = backtests[aggregate].valuation_label
        for result in results:
            write_row(sheet, row, [aggregate, valuation, result.method_name], result.pattern, 3,
                      f.cell("percent"), f.text)
            row += 1
    _widths(sheet, n_tenors, 9)

    # ---- Backtest by tenor -----------------------------------------------------
    sheet = book.add_worksheet("Backtest by tenor")
    _header(sheet, labels + ["row"], n_tenors, tenor_names, f)
    row = 1
    for aggregate, results in results_by_aggregate.items():
        bt = backtests[aggregate]
        if not bt.has_future:
            continue
        key = [aggregate, bt.valuation_label]
        write_row(sheet, row, key + ["actual"], bt.actual_by_tenor, 3, blue_percent, blue)
        row += 1
        counts = [c if c > 0 else None for c in bt.count_by_tenor]
        write_row(sheet, row, key + ["accident periods"], counts, 3, f.cell("integer"), f.text)
        for result in results:
            expected = bt.expected_by_tenor[result.method_name]
            row += 1
            write_row(sheet, row, key + [f"expected {result.method_code}"], expected, 3, f.cell("percent"), f.text)
            row += 1
            write_row(sheet, row, key + [f"difference {result.method_code}"], expected - bt.actual_by_tenor, 3,
                      f.cell("difference_percent"), f.text)
        row += 2
    _widths(sheet, n_tenors, 9)

    # ---- Backtest by period ------------------------------------------------------
    n_periods = max([len(bt.period_labels) for bt in backtests.values()] + [1])
    sheet = book.add_worksheet("Backtest by period")
    _header(sheet, labels + ["row"], n_periods + 1, [f"V+{h}" for h in range(1, n_periods + 1)] + ["total"], f)
    row = 1
    for aggregate, results in results_by_aggregate.items():
        bt = backtests[aggregate]
        if not bt.has_future:
            continue
        key = [aggregate, bt.valuation_label]
        write_row(sheet, row, key + ["period"], bt.period_labels, 3, f.bold, f.text)
        row += 1
        write_row(sheet, row, key + ["actual"], bt.actual_by_period, 3, blue_number, blue)
        write_value(sheet, row, 3 + n_periods, bt.actual_by_period.sum(), blue_number)
        for result in results:
            expected = bt.expected_by_period[result.method_name]
            row += 1
            write_row(sheet, row, key + [f"expected {result.method_code}"], expected, 3, f.cell("number"), f.text)
            write_value(sheet, row, 3 + n_periods, expected.sum(), f.cell("number"))
            row += 1
            difference = expected - bt.actual_by_period
            write_row(sheet, row, key + [f"difference {result.method_code}"], difference, 3,
                      f.cell("difference_number"), f.text)
            write_value(sheet, row, 3 + n_periods, difference.sum(), f.cell("difference_number"))
        row += 2
    _widths(sheet, n_periods + 1, 13)
    book.close()
