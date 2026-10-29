import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from chromainvert.cube import identity_lattice, write_cube
from chromainvert.cube import CubeLut

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("export_graded", ROOT / "scripts" / "export_graded.py")
eg = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(eg)


def _write_cube(path: Path) -> Path:
    write_cube(path, CubeLut(size=2, lattice=identity_lattice(2)))
    return path


def test_escape_space_brackets_and_colon(tmp_path):
    cube = tmp_path / "my lut [v1].cube"
    cube.write_text("x")
    raw = str(cube.resolve()).replace("\\", "/")
    expected = "'" + raw.replace(":", "\\:").replace("[", "\\[").replace("]", "\\]") + "'"
    assert eg.escape_lut3d_path(cube) == expected


def test_apostrophe_cube_rejected_with_clean_error(tmp_path, capsys):
    cube = tmp_path / "my lut's.cube"
    cube.write_text("x")
    with pytest.raises(SystemExit):
        eg.validate_cube(cube)
    assert "apostrophe" in capsys.readouterr().err


def test_escape_space_and_brackets(tmp_path):
    cube = tmp_path / "dir with space" / "grade [v1].cube"
    cube.parent.mkdir(parents=True)
    cube.write_text("x")
    result = eg.escape_lut3d_path(cube)
    assert result.startswith("'") and result.endswith("'")
    assert "\\ " not in result
    assert "\\[" in result and "\\]" in result


def test_resolve_job_cube_reads_bom_json(tmp_path):
    cube = _write_cube(tmp_path / "out.cube")
    job = tmp_path / "job.json"
    job.write_bytes(b'\xef\xbb\xbf{"output_cube": "' + str(cube.name).encode() + b'"}')
    assert eg.resolve_job_cube(job) == cube


def test_resolve_job_cube_rejects_non_object(tmp_path):
    job = tmp_path / "job.json"
    job.write_text("[1, 2]")
    with pytest.raises(SystemExit):
        eg.resolve_job_cube(job)


def test_resolve_paths_two_positional_job_mode(tmp_path):
    cube = _write_cube(tmp_path / "out.cube")
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"output_cube": "out.cube"}))
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    args = eg.build_parser().parse_args([str(src), str(tmp_path / "graded.mp4"), "--job", str(job)])
    input_path, cube_path, output_path = eg.resolve_paths(args)
    assert input_path == src
    assert cube_path == cube
    assert output_path == tmp_path / "graded.mp4"


def test_dry_run_creates_no_directories(tmp_path, capsys):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    cube = _write_cube(tmp_path / "out.cube")
    out = tmp_path / "nested" / "deep" / "graded.mp4"
    rc = eg.main(["--input", str(src), "--cube", str(cube), "--output", str(out), "--dry-run", "--ffmpeg", str(src)])
    assert rc == 0
    assert not (tmp_path / "nested").exists()
    assert ".cube" in capsys.readouterr().out


def test_invalid_fps_rejected(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    cube = _write_cube(tmp_path / "out.cube")
    out = tmp_path / "graded.mp4"
    assert eg.main(["--input", str(src), "--cube", str(cube), "--output", str(out), "--fps", "0", "--dry-run"]) == 1


def test_invalid_preset_rejected():
    with pytest.raises(SystemExit):
        eg.build_parser().parse_args(["--preset", "bogus"])


def test_nonzero_ffmpeg_returns_one_without_raising(tmp_path, monkeypatch, capsys):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    cube = _write_cube(tmp_path / "out.cube")
    out = tmp_path / "graded.mp4"

    class Failed:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda cmd: Failed())
    rc = eg.main(["--input", str(src), "--cube", str(cube), "--output", str(out), "--ffmpeg", str(src)])
    assert rc == 1
    assert "error" in capsys.readouterr().err
