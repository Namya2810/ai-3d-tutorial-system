"""Print a compact health/calibration summary for the latest glove CSV."""

import csv
import statistics
from pathlib import Path


def summarize(path=None):
    log_dir = Path(__file__).resolve().parents[1] / "data" / "glove_sessions"
    if path is None:
        logs = sorted(log_dir.glob("glove_*.csv"), key=lambda item: item.stat().st_mtime)
        if not logs:
            raise FileNotFoundError(f"No glove logs found in {log_dir}")
        path = logs[-1]
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Glove log has no sensor rows: {path}")

    print(f"GLOVE LOG: {path}")
    print(f"Packets: {len(rows)}")
    for finger in ("thumb", "index", "middle", "ring", "pinky"):
        values = [float(row[finger]) for row in rows]
        print(
            f"{finger:>6}: min={min(values):5.1f}%  max={max(values):5.1f}%  "
            f"mean={statistics.fmean(values):5.1f}%"
        )
    bpms = [float(row["pulse_bpm"]) for row in rows if row.get("pulse_bpm")]
    if bpms:
        print(
            f" pulse: min={min(bpms):5.1f}  max={max(bpms):5.1f}  "
            f"mean={statistics.fmean(bpms):5.1f} BPM"
        )
    else:
        print(" pulse: no valid skin-contact BPM samples")
    recenter_count = sum(
        bool(int(row.get("packet_flags") or 0) & 0x01) for row in rows
    )
    print(f"Recenter events: {recenter_count}")
    return rows


if __name__ == "__main__":
    summarize()
