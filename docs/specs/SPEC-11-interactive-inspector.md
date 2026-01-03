# SPEC-11: Interactive Inspector (TUI)

**Status**: PLANNED
**Slice Type**: Vertical (UX/Interpretability)
**Dependencies**: SPEC-08 (Export)
**Priority**: MEDIUM (Usability/Explainability)

---

## 1. Objective

To provide deep transparency into the "Black Box" of the consensus engine. A raw CSV export is insufficient for understanding *why* a specific diagnosis was made, especially when Jurors disagree.

This spec implements a **Terminal User Interface (TUI)** using `textual` to allow researchers to interactively browse, filter, and inspect scored dialogues, acting as a "Visual Debugger" for the psychological assessment process.

---

## 2. Features

### 2.1 The "Courtroom" View
The primary interface is split into three panels:

1.  **The Transcript (Left, 50%)**:
    *   Scrollable view of the dialogue.
    *   **Syntax Highlighting**: Speaker roles (Therapist vs. Client) colored differently.
    *   **Evidence Highlighting**: When a Juror's rationale is selected, the corresponding snippet in the transcript is highlighted (if exact match found).

2.  **The Jury Box (Top Right, 25%)**:
    *   Tabbed view for Juror A, B, C.
    *   Displays: Total Score, Confidence, and Key Rationale bullets.
    *   Visual indicator for "Outlier" (e.g., if Juror A is 10pts away from B and C).

3.  **The Verdict (Bottom Right, 25%)**:
    *   **Posterior Distribution**: ASCII or Block-character bar chart showing the probability distribution of the Total Score.
    *   **Arbitration Status**: Was the Judge invoked? Why? (e.g., "Entropy > 1.2").
    *   **Final Ruling**: The aggregated score and severity.

### 2.2 Filter & Navigation
*   **Smart Filters**:
    *   `Show Disagreements Only` (Range ≥ 2)
    *   `Show Self-Harm Flags`
    *   `Show Arbitrated Cases`
*   **Hotkeys**: `J`/`K` for next/prev dialogue (vim style), `SPACE` to toggle details.

---

## 3. Architecture

### 3.1 Tech Stack
*   **Library**: `textual` (Python TUI framework).
*   **Data Source**: Reads directly from `scored.jsonl` or the SQLite Checkpoint DB. Read-only access.

### 3.2 Component Design

```python
class TranscriptWidget(ScrollableContainer):
    """Renders the dialogue with rich text formatting."""
    def highlight_evidence(self, snippets: list[str]):
        ...

class JuryWidget(Static):
    """Displays the cards for each model."""
    ...

class PosteriorGraph(Static):
    """Renders the probability distribution."""
    def render(self):
        # Use unicode blocks: █ ▆ ▄ ▂
        ...
```

---

## 4. Deliverables

### 4.1 CLI Command

```bash
vibe-check inspect data/outputs/scored.jsonl
```
Launches the full-screen TUI application.

### 4.2 Evidence Mapper
A utility class to fuzzy-match evidence strings back to transcript character offsets for highlighting.
*   *Constraint*: Must be tolerant of minor whitespace/punctuation differences.

---

## 5. Acceptance Criteria

1.  **Performance**: TUI must load and render a 2,000-record dataset in < 1 second.
2.  **Navigation**: Users can rapidly cycle through "Problem Cases" (filtered list) to audit the Judge's performance.
3.  **No Crashing**: Missing fields or malformed records in the JSONL should display a "Corrupted Record" placeholder, not crash the UI.
4.  **Terminal Support**: Must work in standard terminals (xterm-256color) via SSH.

---

## 6. Testing Strategy

*   **Snapshot Testing**: Verify the TUI layout renders correctly for a given state.
*   **Interaction Testing**: Scripted input (simulated keypresses) to verify navigation logic updates the view models.

## 7. Non-Goals

*   **Editing**: The Inspector is Read-Only. No modifying scores or labels.
*   **Remote Web UI**: This is a CLI tool, not a web server. Keeps deployment simple and local.
