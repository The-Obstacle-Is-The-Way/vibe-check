from __future__ import annotations

from vibe_check.calibration.metrics import (
    compute_accuracy,
    compute_cohens_kappa,
    compute_confusion_matrix,
    compute_quadratic_weighted_kappa,
)


def test_metrics_perfect_agreement() -> None:
    y_true = [0, 1, 2, 3, 4]
    y_pred = [0, 1, 2, 3, 4]
    matrix = compute_confusion_matrix(y_true, y_pred, n_classes=5)

    assert compute_accuracy(matrix) == 1.0
    assert compute_cohens_kappa(matrix) == 1.0
    assert compute_quadratic_weighted_kappa(matrix) == 1.0


def test_metrics_detects_disagreement() -> None:
    y_true = [0, 1, 2, 3, 4]
    y_pred = [4, 3, 2, 1, 0]
    matrix = compute_confusion_matrix(y_true, y_pred, n_classes=5)

    assert compute_accuracy(matrix) == 0.2
    assert compute_quadratic_weighted_kappa(matrix) < 0.0
