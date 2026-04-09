import subprocess
import sys
from pathlib import Path


def test_compute_ice_runs(tmp_path):
    # copy sample CSV to tmp and run the script
    repo_root = Path(__file__).resolve().parents[1]
    sample = repo_root / "prioritization_template.csv"
    assert sample.exists()
    inp = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    all_out = tmp_path / "all.csv"
    inp.write_bytes(sample.read_bytes())

    # run compute_ice.py
    script = repo_root / "tools" / "compute_ice.py"
    assert script.exists()
    cmd = [sys.executable, str(script), "--in", str(inp), "--out", str(out), "--all-out", str(all_out), "--force-recalc"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"script failed: {res.stdout}\n{res.stderr}"
    assert out.exists()
    assert all_out.exists()

    # basic checks: header present
    text = out.read_text(encoding="utf-8")
    assert "mapped_status" in text
