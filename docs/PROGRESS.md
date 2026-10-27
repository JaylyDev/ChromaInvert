# ChromaInvert Progress Log

## 2026-10-27: Hackathon plan drafted

Completed:
- Added `docs/CHROMAINVERT_HACKATHON_PLAN.md`: detailed plan extending the initial 3D LUT pipeline spec (product definition, honest problem framing, MVP/Target/Stretch scope, C++/Python contract, engine plan, app plan, spline component, validation and Premiere Pro MCP testing, metrics, team workflow, 36h timeline, risks, demo script, pre-hackathon checklist, open questions).
- Repo state verified: branch `main`, one commit (`Initial commit`), remote `origin` is `https://github.com/JaylyDev/ChromaInvert.git`.

Decisions locked:
- Subprocess plus files interface (job.json in, JSONL progress plus report.json plus .cube out). No embedded Python for the hackathon.
- Vertical slice first: .cube round trip, identity forward pass, benchmark recovery, then GUI wiring.

Next steps:
- Answer the 5 kickoff questions in Section 18 of the plan (duration, team size, demo footage format, demo GPU, Qt vs ImGui).
- Scaffold repo skeleton per Section 12.3 (engine/, app/, assets/, scripts/, work/).
- Implement .cube writer plus FFmpeg lut3d round trip test.
- Smoke test Premiere Pro MCP on the demo machine or fall back to manual checklist.
