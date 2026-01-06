#!/usr/bin/env python3
"""
Deterministic PHQ-8 patch + validation for local DAIC-WOZ label CSVs.

Purpose:
  - Ensure `PHQ8_Score == sum(PHQ8 item columns)` for train/dev (and paper splits).
  - Reconstruct a single missing PHQ8 item value when the authoritative total exists.
  - Ensure `PHQ8_Binary == 1 iff PHQ8_Score >= 10`.

Safety:
  - Defaults to dry-run (no writes).
  - Use `--apply` to write patched CSVs in-place.

Usage:
  uv run python scripts/patch_missing_phq8_values.py --dry-run
  uv run python scripts/patch_missing_phq8_values.py --apply
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PHQ8_ITEM_COLS = [
    "PHQ8_NoInterest",
    "PHQ8_Depressed",
    "PHQ8_Sleep",
    "PHQ8_Tired",
    "PHQ8_Appetite",
    "PHQ8_Failure",
    "PHQ8_Concentrating",
    "PHQ8_Moving",
]


@dataclass(frozen=True)
class FileSpec:
    path: Path
    id_col: str = "Participant_ID"
    total_col: str = "PHQ8_Score"
    binary_col: str = "PHQ8_Binary"
    item_cols: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_cols", list(PHQ8_ITEM_COLS))


def _reconstruct_single_missing_item(
    row: pd.Series,
    *,
    item_cols: list[str],
    total_col: str,
) -> tuple[str, int] | None:
    missing_cols = [c for c in item_cols if pd.isna(row[c])]
    if not missing_cols:
        return None
    if len(missing_cols) > 1:
        raise ValueError(f"Multiple missing PHQ8 items: {missing_cols}")
    missing_col = missing_cols[0]
    if pd.isna(row[total_col]):
        raise ValueError(f"Missing {missing_col} but also missing total {total_col}")

    known_sum = int(pd.Series([row[c] for c in item_cols if c != missing_col]).sum())
    reconstructed = int(row[total_col]) - known_sum
    if reconstructed < 0 or reconstructed > 3:
        raise ValueError(
            f"Reconstructed {missing_col}={reconstructed} out of [0,3] "
            f"(total={int(row[total_col])}, known_sum={known_sum})"
        )
    return missing_col, reconstructed


def _expected_binary(total: pd.Series) -> pd.Series:
    return (total.astype(int) >= 10).astype(int)


def patch_and_validate_csv(spec: FileSpec, *, apply: bool) -> tuple[list[str], list[str]]:
    df = pd.read_csv(spec.path)

    changes: list[str] = []
    problems: list[str] = []

    if spec.id_col not in df.columns:
        problems.append(f"{spec.path}: missing id column {spec.id_col!r}")
        return changes, problems

    missing_any = df[spec.item_cols].isna().any(axis=1)
    for idx in df.index[missing_any]:
        pid = df.at[idx, spec.id_col]
        try:
            reconstructed = _reconstruct_single_missing_item(
                df.loc[idx],
                item_cols=spec.item_cols,
                total_col=spec.total_col,
            )
        except Exception as e:
            problems.append(f"{spec.path}: PID={pid}: cannot reconstruct missing item: {e}")
            continue

        if reconstructed is None:
            continue
        col, value = reconstructed
        old = df.at[idx, col]
        df.at[idx, col] = value
        changes.append(f"{spec.path}: PID={pid}: {col} {old!r} -> {value}")

    if spec.binary_col in df.columns and spec.total_col in df.columns:
        expected = _expected_binary(df[spec.total_col])
        mism = df[spec.binary_col].astype(int) != expected
        for idx in df.index[mism]:
            pid = df.at[idx, spec.id_col]
            old = int(df.at[idx, spec.binary_col])
            new = int(expected.at[idx])
            df.at[idx, spec.binary_col] = new
            changes.append(f"{spec.path}: PID={pid}: {spec.binary_col} {old} -> {new}")

    if spec.total_col in df.columns:
        try:
            sums = df[spec.item_cols].sum(axis=1).astype(int)
            mism = sums != df[spec.total_col].astype(int)
            if mism.any():
                sample = df.loc[mism, [spec.id_col, spec.total_col, *spec.item_cols]].head(10)
                problems.append(
                    f"{spec.path}: sum invariant violated for {int(mism.sum())} rows; sample:\n{sample.to_string(index=False)}"
                )
        except Exception as e:
            problems.append(f"{spec.path}: failed sum-invariant check: {e}")

    if spec.binary_col in df.columns and spec.total_col in df.columns:
        try:
            expected = _expected_binary(df[spec.total_col])
            mism = df[spec.binary_col].astype(int) != expected
            if mism.any():
                sample = df.loc[mism, [spec.id_col, spec.total_col, spec.binary_col]].head(10)
                problems.append(
                    f"{spec.path}: binary invariant violated for {int(mism.sum())} rows; sample:\n{sample.to_string(index=False)}"
                )
        except Exception as e:
            problems.append(f"{spec.path}: failed binary-invariant check: {e}")

    if apply and changes and not problems:
        # Enforce integer dtypes for PHQ columns before writing.
        for col in [spec.binary_col, spec.total_col, *spec.item_cols]:
            if col in df.columns:
                df[col] = df[col].astype(int)
        df.to_csv(spec.path, index=False)

    return changes, problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed changes; do not write files (default).",
    )
    mode.add_argument("--apply", action="store_true", help="Apply deterministic patches in-place.")
    args = parser.parse_args(argv)

    apply = bool(args.apply)

    repo_root = Path(__file__).resolve().parent.parent
    base = repo_root / "data" / "daic-woz"

    specs = [
        FileSpec(path=base / "train_split_Depression_AVEC2017.csv"),
        FileSpec(path=base / "dev_split_Depression_AVEC2017.csv"),
        FileSpec(path=base / "paper_splits" / "paper_split_train.csv"),
        FileSpec(path=base / "paper_splits" / "paper_split_val.csv"),
        FileSpec(path=base / "paper_splits" / "paper_split_test.csv"),
    ]

    missing_files = [str(s.path) for s in specs if not s.path.exists()]
    if missing_files:
        print("ERROR: expected DAIC-WOZ CSVs not found:", file=sys.stderr)
        for p in missing_files:
            print(f"  - {p}", file=sys.stderr)
        return 2

    all_changes: list[str] = []
    all_problems: list[str] = []
    for spec in specs:
        changes, problems = patch_and_validate_csv(spec, apply=apply)
        all_changes.extend(changes)
        all_problems.extend(problems)

    if all_changes:
        header = "APPLIED CHANGES" if apply else "PROPOSED CHANGES (dry-run)"
        print(header)
        for c in all_changes:
            print(f"- {c}")
        print()
    else:
        print("No patches needed.")

    if all_problems:
        print("PROBLEMS", file=sys.stderr)
        for p in all_problems:
            print(p, file=sys.stderr)
        return 2

    if not apply and all_changes:
        return 1

    print("OK: invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
