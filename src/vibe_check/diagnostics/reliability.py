"""Inter-rater reliability metrics for juror scoring (SPEC-07)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeAlias

from krippendorff.krippendorff import alpha

LevelOfMeasurement: TypeAlias = Literal["nominal", "ordinal", "interval", "ratio"]

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy as np


def compute_krippendorff_alpha(
    item_votes: np.ndarray,
    *,
    level_of_measurement: LevelOfMeasurement = "ordinal",
) -> float:
    """Compute Krippendorff's alpha across all items and jurors.

    Args:
        item_votes: Array of shape (n_dialogues, n_items, n_jurors).
        level_of_measurement: "ordinal" for 0-3 PHQ-8 scores.
    """
    if item_votes.ndim != 3:
        raise ValueError("item_votes must be a 3D array (n_dialogues, n_items, n_jurors)")

    n_dialogues, n_items, n_jurors = item_votes.shape
    if n_dialogues < 1 or n_items < 1 or n_jurors < 2:
        raise ValueError("item_votes must contain at least 1 dialogue, 1 item, and 2 jurors")

    reshaped = item_votes.reshape(n_dialogues * n_items, n_jurors)
    value = alpha(
        reshaped.T,
        level_of_measurement=level_of_measurement,
    )
    return float(value)


def compute_krippendorff_alpha_per_item(
    item_votes: np.ndarray,
    *,
    item_names: Sequence[str],
    level_of_measurement: LevelOfMeasurement = "ordinal",
) -> dict[str, float]:
    """Compute Krippendorff's alpha per PHQ-8 item."""
    if item_votes.ndim != 3:
        raise ValueError("item_votes must be a 3D array (n_dialogues, n_items, n_jurors)")
    if item_votes.shape[1] != len(item_names):
        raise ValueError("item_names length must match item_votes.shape[1]")

    out: dict[str, float] = {}
    for idx, name in enumerate(item_names):
        votes_2d = item_votes[:, idx, :]
        value = alpha(votes_2d.T, level_of_measurement=level_of_measurement)
        out[str(name)] = float(value)
    return out
