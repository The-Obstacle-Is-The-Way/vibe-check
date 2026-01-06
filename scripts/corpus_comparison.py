#!/usr/bin/env python3
"""
Corpus Comparison: SQPsychConv vs DAIC-WOZ

Analyzes coverage patterns WITHOUT using labels (no cheating).
Purpose: Detect domain shift risks before spending $600 on scoring.

Usage:
    uv run python scripts/corpus_comparison.py
"""

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

# PHQ-8 keyword heuristics for coverage estimation
# These are NOT labels - just rough proxies for "is this topic discussed?"
PHQ8_KEYWORDS = {
    "anhedonia": [
        r"\b(interest|enjoy|pleasure|fun|hobby|hobbies)\b",
        r"\b(don'?t care|nothing matters|pointless)\b",
    ],
    "depressed_mood": [
        r"\b(depress|sad|down|hopeless|unhappy|miserable|blue)\b",
        r"\b(feeling low|feel down|felt down)\b",
    ],
    "sleep": [
        r"\b(sleep|insomnia|tired|exhausted|rest|awake|wake up)\b",
        r"\b(can'?t sleep|trouble sleeping|sleeping too much)\b",
    ],
    "fatigue": [
        r"\b(tired|fatigue|exhausted|energy|worn out|drained)\b",
        r"\b(no energy|low energy|feel tired)\b",
    ],
    "appetite": [
        r"\b(appetite|eat|eating|food|hungry|weight)\b",
        r"\b(lost appetite|no appetite|overeating|not eating)\b",
    ],
    "guilt": [
        r"\b(guilt|guilty|failure|worthless|blame|fault)\b",
        r"\b(let .* down|disappoint|ashamed)\b",
    ],
    "concentration": [
        r"\b(concentrat|focus|attention|distract|think clearly)\b",
        r"\b(can'?t focus|hard to concentrate|mind wander)\b",
    ],
    "psychomotor": [
        r"\b(slow|restless|fidget|agitat|moving|pace|pacing)\b",
        r"\b(can'?t sit still|feel slow|slowed down)\b",
    ],
}


def count_keyword_matches(text: str, patterns: list[str]) -> int:
    """Count keyword matches in text (case-insensitive)."""
    text_lower = text.lower()
    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, text_lower, re.IGNORECASE))
    return total


def analyze_transcript(text: str) -> dict:
    """Analyze a single transcript for PHQ-8 keyword coverage."""
    results = {}
    for item, patterns in PHQ8_KEYWORDS.items():
        matches = count_keyword_matches(text, patterns)
        results[item] = {
            "matches": matches,
            "mentioned": matches > 0,
        }

    mentioned_count = sum(1 for r in results.values() if r["mentioned"])
    return {
        "items": results,
        "mentioned_count": mentioned_count,
        "coverage": mentioned_count / 8,
        "word_count": len(text.split()),
    }


def load_sqpsychconv_dialogues(path: Path, limit: int | None = None) -> list[dict]:
    """Load SQPsychConv dialogues from Arrow dataset."""
    from datasets import load_from_disk

    ds = load_from_disk(str(path))
    dialogues = []

    for split_name in ["train", "test"]:
        if split_name not in ds:
            continue
        split = ds[split_name]
        for row in split:
            if limit and len(dialogues) >= limit:
                break
            dialogues.append(
                {
                    "id": row["file_id"],
                    "text": row["dialogue"],
                    "source": "sqpsychconv",
                    "split": split_name,
                }
            )

    return dialogues


def load_daicwoz_dialogues(transcripts_path: Path, participant_only: bool = True) -> list[dict]:
    """Load DAIC-WOZ dialogues from transcript CSVs."""
    dialogues = []

    for transcript_dir in sorted(transcripts_path.iterdir()):
        if not transcript_dir.is_dir():
            continue

        csv_files = list(transcript_dir.glob("*_TRANSCRIPT.csv"))
        if not csv_files:
            continue

        csv_path = csv_files[0]
        pid = transcript_dir.name.replace("_P", "")

        try:
            df = pd.read_csv(csv_path, sep="\t")

            if participant_only:
                df = df[df["speaker"] == "Participant"]

            text = " ".join(df["value"].dropna().astype(str).tolist())

            dialogues.append(
                {
                    "id": pid,
                    "text": text,
                    "source": "daicwoz",
                    "participant_only": participant_only,
                }
            )
        except Exception as e:
            print(f"Warning: Failed to load {csv_path}: {e}")

    return dialogues


def compute_corpus_stats(dialogues: list[dict]) -> dict:
    """Compute aggregate statistics for a corpus."""
    analyses = []
    for d in dialogues:
        analysis = analyze_transcript(d["text"])
        analysis["id"] = d["id"]
        analyses.append(analysis)

    # Per-item coverage rates
    item_coverage = {}
    for item in PHQ8_KEYWORDS:
        mentioned = sum(1 for a in analyses if a["items"][item]["mentioned"])
        item_coverage[item] = {
            "mentioned_count": mentioned,
            "mentioned_rate": mentioned / len(analyses) if analyses else 0,
        }

    # Coverage distribution
    coverage_counts = Counter(a["mentioned_count"] for a in analyses)

    # Word count stats
    word_counts = [a["word_count"] for a in analyses]

    return {
        "corpus_size": len(dialogues),
        "item_coverage": item_coverage,
        "coverage_distribution": dict(sorted(coverage_counts.items())),
        "avg_coverage": sum(a["coverage"] for a in analyses) / len(analyses) if analyses else 0,
        "avg_mentioned_items": sum(a["mentioned_count"] for a in analyses) / len(analyses)
        if analyses
        else 0,
        "word_count_stats": {
            "min": min(word_counts) if word_counts else 0,
            "max": max(word_counts) if word_counts else 0,
            "mean": sum(word_counts) / len(word_counts) if word_counts else 0,
            "median": sorted(word_counts)[len(word_counts) // 2] if word_counts else 0,
        },
        "analyses": analyses,
    }


def print_comparison_report(sqpsychconv_stats: dict, daicwoz_stats: dict) -> None:
    """Print a formatted comparison report."""
    print("=" * 70)
    print("CORPUS COMPARISON: SQPsychConv vs DAIC-WOZ")
    print("=" * 70)
    print()

    print("## Corpus Sizes")
    print(f"  SQPsychConv: {sqpsychconv_stats['corpus_size']:,} dialogues")
    print(f"  DAIC-WOZ:    {daicwoz_stats['corpus_size']:,} dialogues")
    print()

    print("## Word Count Statistics")
    print(f"  {'Metric':<15} {'SQPsychConv':>15} {'DAIC-WOZ':>15}")
    print(f"  {'-' * 15} {'-' * 15} {'-' * 15}")
    for metric in ["min", "max", "mean", "median"]:
        sq_val = sqpsychconv_stats["word_count_stats"][metric]
        dw_val = daicwoz_stats["word_count_stats"][metric]
        print(f"  {metric:<15} {sq_val:>15,.0f} {dw_val:>15,.0f}")
    print()

    print("## Average PHQ-8 Item Coverage (keyword heuristic)")
    print(
        f"  SQPsychConv: {sqpsychconv_stats['avg_mentioned_items']:.2f}/8 items ({sqpsychconv_stats['avg_coverage'] * 100:.1f}%)"
    )
    print(
        f"  DAIC-WOZ:    {daicwoz_stats['avg_mentioned_items']:.2f}/8 items ({daicwoz_stats['avg_coverage'] * 100:.1f}%)"
    )
    print()

    print("## Per-Item Coverage Rates")
    print(f"  {'Item':<20} {'SQPsychConv':>15} {'DAIC-WOZ':>15} {'Δ':>10}")
    print(f"  {'-' * 20} {'-' * 15} {'-' * 15} {'-' * 10}")
    for item in PHQ8_KEYWORDS:
        sq_rate = sqpsychconv_stats["item_coverage"][item]["mentioned_rate"]
        dw_rate = daicwoz_stats["item_coverage"][item]["mentioned_rate"]
        delta = sq_rate - dw_rate
        delta_str = f"{delta:+.1%}" if abs(delta) > 0.05 else "~"
        print(f"  {item:<20} {sq_rate:>14.1%} {dw_rate:>14.1%} {delta_str:>10}")
    print()

    print("## Coverage Distribution (# items mentioned per dialogue)")
    print(f"  {'Items':<10} {'SQPsychConv':>15} {'DAIC-WOZ':>15}")
    print(f"  {'-' * 10} {'-' * 15} {'-' * 15}")
    all_counts = set(sqpsychconv_stats["coverage_distribution"].keys()) | set(
        daicwoz_stats["coverage_distribution"].keys()
    )
    for count in sorted(all_counts):
        sq_n = sqpsychconv_stats["coverage_distribution"].get(count, 0)
        dw_n = daicwoz_stats["coverage_distribution"].get(count, 0)
        sq_pct = (
            sq_n / sqpsychconv_stats["corpus_size"] * 100 if sqpsychconv_stats["corpus_size"] else 0
        )
        dw_pct = dw_n / daicwoz_stats["corpus_size"] * 100 if daicwoz_stats["corpus_size"] else 0
        print(f"  {count:<10} {sq_n:>6} ({sq_pct:>5.1f}%) {dw_n:>6} ({dw_pct:>5.1f}%)")
    print()

    print("## Domain Shift Assessment")
    coverage_delta = abs(sqpsychconv_stats["avg_coverage"] - daicwoz_stats["avg_coverage"])
    if coverage_delta < 0.1:
        print("  ✅ Coverage patterns are SIMILAR (Δ < 10%)")
    elif coverage_delta < 0.2:
        print("  ⚠️ Coverage patterns show MODERATE difference (10% < Δ < 20%)")
    else:
        print("  ❌ Coverage patterns show SIGNIFICANT difference (Δ > 20%)")
    print()

    # Flag items with >15% difference
    flagged = []
    for item in PHQ8_KEYWORDS:
        sq_rate = sqpsychconv_stats["item_coverage"][item]["mentioned_rate"]
        dw_rate = daicwoz_stats["item_coverage"][item]["mentioned_rate"]
        if abs(sq_rate - dw_rate) > 0.15:
            flagged.append((item, sq_rate, dw_rate))

    if flagged:
        print("  Items with >15% coverage difference:")
        for item, sq, dw in flagged:
            print(f"    - {item}: SQ={sq:.1%}, DW={dw:.1%}")
    else:
        print("  No items with >15% coverage difference.")
    print()


def main():
    """Run corpus comparison analysis."""
    base_path = Path(__file__).parent.parent

    # Load SQPsychConv
    sqpsychconv_path = base_path / "data" / "sqpsychconv" / "qwen-2.5"
    if not sqpsychconv_path.exists():
        print(f"ERROR: SQPsychConv not found at {sqpsychconv_path}")
        print("Download with: datasets.load_dataset('AIMH/SQPsychConv_qwen-2.5')")
        return

    print("Loading SQPsychConv...")
    sqpsychconv_dialogues = load_sqpsychconv_dialogues(sqpsychconv_path)
    print(f"  Loaded {len(sqpsychconv_dialogues)} dialogues")

    # Load DAIC-WOZ
    daicwoz_path = base_path / "data" / "daic-woz" / "transcripts_participant_only"
    if not daicwoz_path.exists():
        daicwoz_path = base_path / "data" / "daic-woz" / "transcripts"

    if not daicwoz_path.exists():
        print(f"ERROR: DAIC-WOZ not found at {daicwoz_path}")
        return

    print("Loading DAIC-WOZ...")
    daicwoz_dialogues = load_daicwoz_dialogues(daicwoz_path, participant_only=True)
    print(f"  Loaded {len(daicwoz_dialogues)} dialogues")

    # Compute stats
    print("\nAnalyzing SQPsychConv...")
    sqpsychconv_stats = compute_corpus_stats(sqpsychconv_dialogues)

    print("Analyzing DAIC-WOZ...")
    daicwoz_stats = compute_corpus_stats(daicwoz_dialogues)

    # Print report
    print()
    print_comparison_report(sqpsychconv_stats, daicwoz_stats)

    # Save detailed results
    output_path = base_path / "data" / "outputs" / "corpus_comparison.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove analyses (too large) for JSON export
    sqpsychconv_export = {k: v for k, v in sqpsychconv_stats.items() if k != "analyses"}
    daicwoz_export = {k: v for k, v in daicwoz_stats.items() if k != "analyses"}

    with output_path.open("w") as f:
        json.dump(
            {
                "sqpsychconv": sqpsychconv_export,
                "daicwoz": daicwoz_export,
            },
            f,
            indent=2,
        )

    print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
