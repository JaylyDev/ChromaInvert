# Asset Sources

No third party assets are committed yet. Every file added under `assets/` must be listed here with its source and license.

## Demo footage (local only, not committed)

Local sample pack at `C:\Users\lokwa\Documents\SampleFootage`, kept out of git.
Used by `scripts/run_demo.py` and `docs/DEMO_SCRIPT.md` for the dry run.

- `Rec709/A001_10290006_C101.mov`: Rec.709 H.265 clip, 3840x2160, about 9.4 s.
  Passed as `--source` in the demo commands. Contract v1 decodes it as `rec709`.
- `Apple Log/A001_10290006_C100.mov`: Apple Log H.265 clip, BT.2020, about 8.7 s.
  Passed as `--reference` in the demo commands. Decoded as `rec709` display-referred for
  the demo only; true Apple Log working space is roadmap.
- `S-log3/` directory: six ProRes 4444 S-Log3 clips. Not used in the default
  dry run because contract v1 rejects `slog3`; reserved for the bounded log
  working-space milestone.

Provenance: operator supplied test footage. License: all rights reserved by the
footage owner, do not redistribute or commit to git.

## Tracked samples

- `assets/job.json.example`: ChromaInvert sample job (contract v1, rec709). Authored in repo, no license restriction.
