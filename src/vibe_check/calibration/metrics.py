"""Agreement metrics for human calibration (SPEC-09)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def compute_confusion_matrix(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    *,
    n_classes: int,
) -> list[list[int]]:
    """Compute an `n_classes x n_classes` confusion matrix.

    Rows are true labels, columns are predicted labels.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if n_classes < 2:
        raise ValueError("n_classes must be >= 2")

    matrix: list[list[int]] = [[0 for _ in range(n_classes)] for _ in range(n_classes)]
    for t, p in zip(y_true, y_pred, strict=True):
        if not (0 <= t < n_classes):
            raise ValueError(f"y_true label out of range: {t}")
        if not (0 <= p < n_classes):
            raise ValueError(f"y_pred label out of range: {p}")
        matrix[t][p] += 1
    return matrix


def compute_accuracy(confusion_matrix: Sequence[Sequence[int]]) -> float:
    total = 0
    correct = 0
    for i, row in enumerate(confusion_matrix):
        for j, value in enumerate(row):
            total += int(value)
            if i == j:
                correct += int(value)
    if total == 0:
        raise ValueError("confusion_matrix has zero total count")
    return correct / total


def compute_cohens_kappa(confusion_matrix: Sequence[Sequence[int]]) -> float:
    """Compute Cohen's kappa from a confusion matrix (unweighted)."""
    n = len(confusion_matrix)
    if n < 2:
        raise ValueError("confusion_matrix must have at least 2 classes")
    if any(len(row) != n for row in confusion_matrix):
        raise ValueError("confusion_matrix must be square")

    row_sums = [sum(int(v) for v in row) for row in confusion_matrix]
    col_sums = [sum(int(confusion_matrix[i][j]) for i in range(n)) for j in range(n)]
    total = sum(row_sums)
    if total == 0:
        raise ValueError("confusion_matrix has zero total count")

    p_o = sum(int(confusion_matrix[i][i]) for i in range(n)) / total
    p_e = sum((row_sums[i] / total) * (col_sums[i] / total) for i in range(n))
    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)


def compute_quadratic_weighted_kappa(confusion_matrix: Sequence[Sequence[int]]) -> float:
    """Compute quadratic weighted Cohen's kappa from a confusion matrix."""
    n = len(confusion_matrix)
    if n < 2:
        raise ValueError("confusion_matrix must have at least 2 classes")
    if any(len(row) != n for row in confusion_matrix):
        raise ValueError("confusion_matrix must be square")

    row_sums = [sum(int(v) for v in row) for row in confusion_matrix]
    col_sums = [sum(int(confusion_matrix[i][j]) for i in range(n)) for j in range(n)]
    total = sum(row_sums)
    if total == 0:
        raise ValueError("confusion_matrix has zero total count")

    denom = (n - 1) ** 2
    # Observed weighted disagreement
    obs = 0.0
    for i in range(n):
        for j in range(n):
            w = ((i - j) ** 2) / denom
            obs += w * int(confusion_matrix[i][j])
    obs /= total

    # Expected weighted disagreement under independence
    exp = 0.0
    for i in range(n):
        for j in range(n):
            w = ((i - j) ** 2) / denom
            expected_ij = (row_sums[i] * col_sums[j]) / total
            exp += w * expected_ij
    exp /= total

    if exp == 0.0:
        return 1.0
    return 1.0 - (obs / exp)
