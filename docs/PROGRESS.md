# ChromaInvert Progress Log

## 2026-10-27: Hackathon plan drafted

Completed:
- Added `docs/CHROMAINVERT_HACKATHON_PLAN.md`: detailed plan extending the initial 3D LUT pipeline spec (product definition, honest problem framing, MVP/Target/Stretch scope, C++/Python contract, engine plan, app plan, spline component, validation and Premiere Pro MCP testing, metrics, team workflow, 36h timeline, risks, demo script, pre-hackathon checklist, open questions).
- Repo state verified: branch `main`, one commit (`Initial commit`), remote `origin` is `https://github.com/JaylyDev/ChromaInvert.git`.

Decisions locked:
- Subprocess plus files interface (job.json in, JSONL progress plus report.json plus .cube out). No embedded Python for the hackathon.
- Vertical slice first: .cube round trip, identity forward pass, benchmark recovery, then GUI wiring.

Next steps:
- Feature 2: DifferentiableLUT3D identity forward pass (`engine/chromainvert/lut_module.py` plus test).

## 2026-10-27: Feature 1, .cube read/write engine

Completed:
- Added `engine/chromainvert/cube.py` with `CubeLut`, `identity_lattice`, `write_cube`, `read_cube`. Red varies fastest in file order, matching FFmpeg `lut3d` expectations. Writer clamps to [0, 1].
- Added `engine/tests/test_cube_roundtrip.py`, `scripts/validate_cube.py`, plus project skeleton (`README.md`, `.gitignore`, `engine/pyproject.toml`, `assets/SOURCES.md`).

Verified:
- `python -m pytest engine/tests -q`: 5 passed (round trip at sizes 2, 17, 33, axis order, domain, rejection of bad files, writer validation).
- `python scripts/validate_cube.py`: PASS. Identity 33 LUT applied with FFmpeg `lut3d` gives pixel-identical output (peak diff 0.0). Channel-swap LUT turns pure red into blue, confirming lattice axis order matches FFmpeg.

