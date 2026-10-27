# ChromaInvert: Detailed Hackathon Plan

Status: planning document, extends the initial technical architecture spec
Assumption stated up front: 36 hour hackathon, 2 core developers (Python/color and C++/app), plus optional floating help for testing, demo assets, and presentation. Scaling notes for 24 and 48 hours are in Section 14. If the team or duration differs, cut from the stretch list first, never from the end-to-end slice in Section 5.

Success in one sentence: a judge can pick an ungraded clip and a reference frame, click Match, watch progress, preview a stable graded result with before/after and scopes, and export a `.cube` that loads in FFmpeg, DaVinci Resolve, and Premiere Pro and produces the same grade there.

---

## 1. Product Definition

### 1.1 Problem

Matching a reference grade by hand means balancing curves, wheels, and hue qualifiers while chasing scopes. Per-frame AI style transfer is fast but temporally unstable: identical colors in adjacent frames map differently, so video flickers. A 3D LUT is the opposite: one fixed function of input color only, applied identically to every frame. If ChromaInvert recovers a good LUT, temporal stability is guaranteed by construction, and the result is portable to any editor.

### 1.2 Core claim to prove in the demo

1. Differentiable optimization recovers a smooth 3D LUT from one reference frame in seconds, not a neural per-pixel edit.
2. The exported `.cube` alone reproduces the look in a third party tool. The demo must show the FFmpeg/Resolve/Premiere result, not only the in-app preview, so judges see there is no hidden per-frame AI.
3. Skin tones and shadows survive: the grade does not push faces orange/green or crush shadow detail.

### 1.3 Non-goals for the hackathon

- Recovering the true original camera RAW data or the true original grading node tree. This is mathematically underdetermined from a compressed frame; ChromaInvert recovers a LUT that is perceptually equivalent on the target footage, and the pitch must say exactly that.
- Shot detection, per-shot LUTs, tracking, relighting, denoising, HDR mastering, or a full NLE.
- Training a neural network. There is no training dataset and no training phase; the LUT lattice itself is the optimized parameter set.
- Bulletproof handling of every camera log format on day one. Support is tiered in Section 7.

---

## 2. The Hard Problem, Stated Honestly

### 2.1 Why naive matching fails

The source frame and the reference frame show different scenes. There is no pixel correspondence, so a pixelwise loss (MSE between graded source and reference) is meaningless and will produce garbage. What transfers between scenes is the color transform, observed only indirectly through each scene's color distribution.

Therefore the objective is distribution matching under anchors:

- Match the graded source distribution to the reference distribution in a perceptual space (luminance CDF, chroma/hue histograms, channel quantiles and moments in Oklab or CIE Lab).
- Keep the transform plausible everywhere, including colors absent from both frames, via identity initialization and smoothness regularization. Unseen lattice regions must default to a smooth extension of the seen grade, not random colors. This is the most common failure mode and the main demo risk.
- Anchor protected regions (skin, near-neutral shadows) so distribution matching does not sacrifice faces to satisfy a global histogram.

### 2.2 Evaluation trick that makes this verifiable

Synthetic ground truth benchmark, built before any UI polish:

1. Take an ungraded frame `S`. Apply a known commercial-style `.cube` `G` with FFmpeg `lut3d` to make reference `R = G(S2)` from a different frame `S2` of similar content.
2. Run ChromaInvert on `(S, R)` to produce recovered LUT `L`.
3. Grade: apply `L` to held-out frames and compare against `G` applied to the same frames using mean DeltaE2000, PSNR, and histogram distance. Also compare `L` vs `G` directly on a dense RGB lattice sweep and on a standard color chart image.

This gives a numeric success criterion (Section 11) instead of "looks good to us at 3 a.m."

### 2.3 Interpolation: trilinear, tetrahedral, and splines

- Optimization uses trilinear sampling (`F.grid_sample`, mode bilinear on a 5D volume; see Section 6.2) because it is differentiable and fast.
- Delivery tools differ: Resolve and Premiere effectively evaluate `.cube` LUTs with tetrahedral interpolation. A LUT optimized only under trilinear can shift slightly in tetrahedral evaluation. Mitigation: after optimization, evaluate the final lattice densely under both schemes on test colors and report max DeltaE; if the gap is visible, add a fine-tune pass that samples with a tetrahedral approximation or simply accept and document the measured gap.
- Spline role (from the camera-path analogy): optimize a coarse lattice (17x17x17) for speed and stability, then upsample to 33x33x33 with separable Catmull-Rom cubic splines for a smooth export, with clamped overshoot so spline ringing never pushes values out of gamut. Alternative: optimize at 33 directly if GPU time allows; decide from the first benchmark, not by preference. Splines also fit the optional 1D pre-curves (per-channel tone curves) placed before the 3D lattice.

---

## 3. Scope: MVP, Target, Stretch

### 3.1 MVP (must ship, demoable even if everything else is cut)

- [ ] Desktop app opens, user selects: source video or image, reference image, output folder.
- [ ] App extracts representative source frames (FFmpeg) and hands frames plus a JSON job file to the Python engine as a subprocess.
- [ ] Engine optimizes a 3D LUT (identity init, distribution loss, total variation smoothness) and exports a valid 33x33x33 `.cube`.
- [ ] App applies the `.cube` with FFmpeg `lut3d`, shows before/after stills and a short preview clip, and exports a graded MP4.
- [ ] CLI fallback for the whole pipeline with no GUI, so the demo survives a GUI failure.
- [ ] Synthetic benchmark runs and prints DeltaE numbers for the README and pitch.

### 3.2 Target (expected if MVP lands by midpoint)

- [ ] Skin/shadow anchoring (heuristic mask first, segmentation if time), loss curve and progress streamed to the GUI.
- [ ] Scopes in app: RGB parade or waveform, vectorscope, luminance histogram, source vs graded vs reference.
- [ ] Color input handling: Rec.709, S-Log3, and one of V-Log/LogC selectable; HLG and Rec.2020 tagged inputs detected and converted (Section 7).
- [ ] Strength slider (blend LUT toward identity), LUT size selector (17/33), and re-export without re-optimizing.
- [ ] Premiere Pro validation via MCP-driven test (Section 10.3) plus a manual Resolve checklist as fallback.

### 3.3 Stretch (only after Target is green)

- [ ] 1D spline pre-curves plus 3D lattice joint optimization.
- [ ] Multi-frame reference (average distribution over 3 to 5 reference frames) and multi-shot source sampling.
- [ ] Embedded Python (pybind11/PyTorch C++) instead of subprocess; live LUT preview while optimizing.
- [ ] Batch mode: one reference, many clips. Linux build verified in CI or a VM.

---

## 4. System Architecture

```
+------------------------- C++ desktop app -------------------------+
| file pickers | job runner | preview (FFmpeg lut3d) | scopes | log |
+----+--------------------+----------------------+------------------+
     | writes             | reads                | reads
     v                    v                      v
  workdir/job.json   workdir/progress.jsonl   workdir/out.cube
  workdir/src_*.png  (engine stdout mirror)   workdir/graded.mp4
     |                    ^                      ^
+----+--------------------+----------------------+--- Python engine -+
| frame sampling | DifferentiableLUT3D | losses | .cube export      |
| masks (skin/shadow) | Adam loop | metrics + benchmark mode        |
+--------------------------------------------------------------------+
```

### 4.1 Interface contract (freeze this in hour 1, both devs sign off)

Process model for the hackathon: subprocess plus files. No shared memory, no embedded interpreter, no sockets. Rationale: independently debuggable, the CLI is the contract, and either side can be developed against canned files.

`job.json` written by C++ (or the CLI):

```json
{
  "job_id": "demo01",
  "source_frames": ["work/src_000.png", "work/src_001.png"],
  "reference_frames": ["work/ref_000.png"],
  "input_profile": "slog3_sgamut3cine",
  "working_space": "rec709_scene",
  "lut_size": 33,
  "coarse_size": 17,
  "iterations": 400,
  "strength": 1.0,
  "seed": 42,
  "output_cube": "work/out.cube",
  "report_json": "work/report.json"
}
```

Engine guarantees:

- Exit code 0 on success, nonzero with a final `{"event":"error","message":"..."}` line on failure.
- Progress on stdout as JSON Lines, flushed per line, e.g. `{"event":"progress","iter":120,"iters":400,"loss":0.031,"elapsed_s":1.8}` and `{"event":"done","cube":"work/out.cube","seconds":4.2}`. C++ parses line by line to drive the progress bar; no regex on prose logs.
- `report.json` with final loss terms, DeltaE self-check numbers, lattice stats (min/max, max neighbor delta), device used (cuda/cpu), and library versions. This file feeds the demo screen and the bug reports.
- Deterministic given `seed` and identical inputs.

Frame exchange format: 16-bit PNG for stills (or half-float EXR if OpenEXR is already available; do not add it speculatively). State the assumed transfer function in `job.json`; never guess silently in code.

### 4.2 Why not embedded Python first

Embedding (Python C API or pybind11 plus Torch) couples crash domains, build systems, and GPU DLL loading, and typically eats half a hackathon. Subprocess keeps the C++ app shippable even with a CPU-only engine. Embedding is a stretch item only.

---

## 5. Build Order: The Vertical Slice First

Rule: no component is "done" alone. Build in this order and keep the pipeline runnable after every step.

1. `.cube` writer plus reader round-trip in Python, validated by FFmpeg `lut3d` on a test image. Verify: FFmpeg applies the exported identity LUT and the output is pixel-identical (or within 1 code value) to the input.
2. `DifferentiableLUT3D` forward pass with identity lattice reproduces the input image. Verify: unit test, max abs error below 1e-5.
3. Optimizer with distribution loss on the synthetic benchmark (Section 2.2), CLI only. Verify: recovered LUT beats identity baseline on held-out DeltaE.
4. C++ FFmpeg frame extraction plus `lut3d` preview of a hardcoded `.cube`. Verify: app shows graded frame.
5. Connect 3 and 4 through `job.json`. This is the MVP. Verify: full click-to-graded-preview run.
6. Only then: masks, scopes polish, extra color profiles, Premiere MCP tests.

---

## 6. Python Engine Plan (Owner: Python/Color Developer)

### 6.1 Project layout

```
engine/
  pyproject.toml            # pinned deps: torch, numpy, colour-science, opencv or imageio
  chromainvert/
    cube.py                 # .cube read/write, lattice reshape, validation
    lut_module.py           # DifferentiableLUT3D (nn.Module)
    color.py                # sRGB/linear, Lab/Oklab conversions, log decoders
    losses.py               # distribution, TV smoothness, skin/shadow anchors
    masks.py                # skin heuristic, shadow mask, optional segmentation
    optimize.py             # Adam loop, sampling, progress JSONL, report.json
    spline.py               # Catmull-Rom upsample 17 -> 33, 1D pre-curves
    benchmark.py            # synthetic ground-truth recovery benchmark
    cli.py                  # argparse entry: chromainvert run job.json
  tests/
    test_cube_roundtrip.py
    test_lut_identity.py
    test_benchmark_recovery.py
assets/                     # test frames, charts, known .cube files, licenses noted
```

### 6.2 DifferentiableLUT3D: exact tensor contract

- Learnable parameter: lattice of shape `(33, 33, 33, 3)`, stored for `grid_sample` as volume `(1, 3, 33, 33, 33)` with channel order RGB and spatial axes ordered (B, G, R) to match the `.cube` file order (red varies fastest in the file; lattice index order must be unit-tested against FFmpeg, this mismatch is the classic silent bug).
- Forward: normalize source pixels `(N, H, W, 3)` in `[0, 1]` to grid coordinates in `[-1, 1]`, reshape to `(1, P, 1, 1, 3)`, call `F.grid_sample(volume, grid, mode="bilinear", padding_mode="border", align_corners=True)`. `padding_mode="border"` clamps out-of-range colors to the lattice edge instead of zeroing them.
- Initialize to the identity lattice plus zero noise. Any other init makes unseen colors unpredictable.
- Optimize coarse (17) then spline-upsample and optionally fine-tune at 33 (Section 2.3). Clamp or softly constrain outputs to `[0, 1]` in the loss; clamp hard only at export.
- Pixel budget: subsample at most ~65k pixels per frame (random, seeded) and 1 to 5 frames per iteration batch. Full 4K frames in the loop are wasted compute; the LUT only sees colors, not positions (masks excepted).

### 6.3 Losses (weighted sum, weights in job config, logged per term)

1. Distribution loss (primary): differentiable soft histograms (Gaussian kernel binning) per Oklab channel plus 2D chroma histogram (a-b plane), and luminance quantile matching (sorted sample quantiles, L1). Start with moments plus quantiles if soft histograms run long; measure, then decide.
2. Smoothness: total variation on the lattice (mean absolute difference between neighboring lattice points, all 3 axes). This is what prevents banding and wild unseen colors.
3. Identity prior (small weight, decays over iterations): keeps sparsely observed regions sane early.
4. Skin anchor: masked pixels whose reference-side expected skin chroma (from reference skin pixels if present, else a canonical skin locus in Lab) should stay within a DeltaE budget; implemented as a soft penalty on skin-masked graded pixels drifting from their input hue/chroma beyond a tolerance.
5. Shadow anchor: penalty on crushing near-black detail: graded luminance of shadow-masked pixels should preserve local ordering/spread, approximated by matching shadow luminance quantiles between graded source shadows and reference shadows.
6. Gamut penalty: soft penalty for outputs outside `[0, 1]`.

Optimizer: Adam, lr 0.01 to 0.05 with cosine decay, 300 to 600 iterations target, early stop when total loss plateaus. Log every term; a single scalar loss hides which anchor is fighting the distribution match.

### 6.4 Masks: pragmatic ladder

1. First: skin heuristic in YCbCr/HSV range plus luminance gating, morphologically cleaned. Works on the demo footage or it does not ship.
2. Shadow mask: lowest luminance decile with low chroma saturation thresholding.
3. Only if time: torchvision segmentation (e.g. DeepLab/FastSCNN class models or a face parser) to refine skin. Pre-download weights before the event; assume venue Wi-Fi is unreliable (see risks).

### 6.5 Color science rules

- Do all optimization in a declared working space. Default pipeline: decode input to linear, convert to the working space, optimize the LUT in display-referred Rec.709 code values (because that is what a `.cube` applied in an editor will see after the editor's own input transform), and document this on the export screen.
- Use `colour-science` for Lab/Oklab/XYZ conversions and DeltaE2000; do not hand-roll color matrices except the documented log decoders, which get unit tests against known values.
- Validate the `.cube` writer against the IRIDAS/Adobe `.cube` spec subset: `TITLE`, `LUT_3D_SIZE 33`, optional `DOMAIN_MIN/DOMAIN_MAX` (default 0 to 1, omit unless needed), red-fastest data order, values in `[0, 1]`.

### 6.6 Performance targets

- 1080p sampled inputs, 17-cube coarse opt: under 5 s on a midrange NVIDIA GPU, under 30 s CPU fallback with reduced iterations and pixel count (auto-degrade, report it in the UI; never hang silently).
- Export `.cube` under 1 s. Applying the LUT to video is FFmpeg's job, not PyTorch's.

---

## 7. Color Input/Output Workflows (Shared, Python leads)

### 7.1 Supported input profiles, tiered

| Tier | Input | Handling |
|---|---|---|
| 1 (MVP) | Rec.709 / sRGB stills and video | Use as-is in `[0, 1]`; tag assumed profile in UI |
| 1 | S-Log3 / S-Gamut3.Cine | Published decode curve to linear, matrix to Rec.709 primaries, then working-space encode; unit-tested curve |
| 2 (Target) | V-Log or LogC (pick one by team footage), generic "log, gamma only" custom curve | Same pattern |
| 2 | HLG (Rec.2020) | Read FFmpeg stream metadata (primaries/transfer/matrix); HLG inverse OOTF approximation to scene linear, Rec.2020 to Rec.709 gamut conversion; label result "preview quality" if gamut mapping is simple clipping |
| 3 (Stretch) | PQ HDR, ACES, RAW video | Out of scope to grade natively; convert with FFmpeg tonemap to Rec.709 first and say so |

Rule: FFmpeg stream color metadata is read and displayed in the app (primaries, transfer, matrix, range). If metadata is missing or "unknown", the user picks the profile manually; the app never silently assumes BT.709 for a log file. Full-range vs limited-range mishandling is a top-three silent quality bug: normalize range explicitly during frame extraction and test with a known chart.

### 7.2 Output

- `.cube` 33 (default) or 17, plus the graded preview MP4 (H.264, Rec.709 tags written explicitly) from FFmpeg `lut3d`.
- A one-page `report.json` and human-readable summary: input profiles, iterations, seconds, device, loss terms, benchmark DeltaE if run.
- Note for judges: the same `.cube` in Resolve/Premiere is the portability proof. Keep one graded frame exported from Premiere in the slide deck (Section 10.3).

---

## 8. C++ Desktop App Plan (Owner: C++/FFmpeg Developer)

### 8.1 Stack decision (decide in hour 1, do not revisit)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Qt 6 + CMake + vcpkg | Real file dialogs, sliders, image panes, cross-platform, good video widget story | Heavier setup, licensing awareness (LGPL fine for hackathon) | Recommended if either dev has used Qt before |
| Dear ImGui + GLFW/SDL | Fastest to first window, great for scopes/plots (ImPlot) | File dialogs and video preview are DIY, looks like a tool not a product | Recommended if no Qt experience; speed wins hackathons |
| CLI only + web demo page | Zero GUI risk | Weaker demo, no scrub/preview story | Fallback only, kept working regardless (Section 5) |

FFmpeg integration, two levels:

1. MVP: invoke `ffmpeg`/`ffprobe` executables as subprocesses for frame extraction, `lut3d` application, and encode. Radically simpler than linking, identical filters, and the commands can be shown in the UI log for credibility.
2. Target: link `libavformat/libavcodec/libswscale` via vcpkg for in-app decode, scrubbing, and real-time preview. Only attempt after the subprocess pipeline demos end to end.

### 8.2 Project layout

```
app/
  CMakeLists.txt            # C++17, vcpkg toolchain, Qt6 or ImGui+GLFW, FFmpeg (target level 2)
  vcpkg.json
  src/
    main.cpp
    MainWindow.* / App.*    # layout: inputs, Match button, progress, exports
    JobRunner.*             # writes job.json, spawns engine, parses JSONL progress
    Ffmpeg.*                # probe metadata, extract frames, apply lut3d, encode
    Preview.*               # before/after panes, slider wipe, playback/scrub
    Scopes.*                # histogram, parade/waveform, vectorscope (target)
assets/ icons, sample project
```

### 8.3 UI: one screen, demo-first

- Left: Source (thumbnail/clip name, detected color metadata, profile dropdown), Reference (image, "use frame from video" option).
- Center: large before/after preview with wipe slider; below it transport (play/pause, scrub) for the preview clip.
- Right: Match button, progress bar with iteration and loss, device badge (GPU/CPU), Strength slider, LUT size, Export `.cube`, Export graded MP4, Open in folder.
- Bottom: collapsible log pane showing the exact ffmpeg commands and engine JSONL tail. Judges and engineers trust visible pipelines.
- Scopes (target): four small panels: reference histogram, graded histogram, vectorscope overlay, loss curve. If time forces a cut, keep histograms and drop the vectorscope rendering, but keep the vectorscope numbers in `report.json`.

### 8.4 C++ responsibilities checklist

- [ ] CMake + vcpkg build green on the demo laptop first, second OS only if time (Windows primary; Linux is "also builds" honesty, not a promise).
- [ ] `ffprobe` metadata parse: codec, resolution, fps, primaries/transfer/matrix/range; display and pass to job file.
- [ ] Frame extraction: scene-representative sampling (e.g. 5 frames spread over the clip, or thumb at 25/50/75 percent), 16-bit PNG to workdir, range-normalized.
- [ ] Engine subprocess with streamed stdout parsing, cancel button (kill process cleanly), timeout with a clear error.
- [ ] Preview encode: `ffmpeg -i src -vf lut3d=file=out.cube` (plus format conversion), H.264 Rec.709 tagged output; before/after frame grabs at identical timestamps.
- [ ] Error surfaces: missing FFmpeg, missing Python env, GPU absent: each gets a plain-language dialog plus log line, tested once deliberately.

### 8.5 Packaging

- A `run_demo.bat` / `run_demo.sh` and a README quickstart that works from a clean checkout: Python venv creation, pinned `requirements`, FFmpeg on PATH check, sample assets included.
- Freeze the demo machine early: install everything, run the full pipeline, then change nothing on it except code. Keep a second laptop able to run the CLI pipeline as backup.

---

## 9. Spline Interpolation Component (Shared, small and testable)

Origin: the same cubic-spline machinery used to smooth camera paths applies to LUT lattice upsampling and tone curves.

- `spline.py`: separable Catmull-Rom over each lattice axis (17 to 33), applied per output channel; clamp overshoot to the convex hull of neighbors to prevent ringing outside `[0, 1]`.
- Unit tests: upsampling an identity lattice returns identity within tolerance; upsampling preserves lattice corner values; a monotone 1D ramp stays monotone after clamp.
- Optional target feature: 1D per-channel spline pre-curves (8 to 16 control points, monotone-constrained) optimized jointly before the 3D lattice, which often captures 80 percent of a film look (contrast S-curve plus channel rebalance) and makes the 3D stage's job easier. Present this in the pitch as "coarse tone spline plus fine color lattice", it is a genuinely good story.
- Document the tetrahedral check (Section 2.3) as a known measured quantity, not a surprise.

---

## 10. Validation and Premiere Pro MCP Testing

### 10.1 Automated tests (run before every demo rehearsal)

- Python: cube round-trip, identity forward pass, spline identity/monotonicity, log-decoder known values, benchmark recovery beats identity by the Section 11 margin.
- Pipeline: golden job on checked-in sample frames produces a `.cube` whose FFmpeg-applied output matches stored reference frames within tolerance (guards the R-fastest ordering bug forever).
- Manual smoke: fresh workdir, full GUI run, export, open `.cube` in one external tool.

### 10.2 External tool matrix

| Tool | Test | Pass condition |
|---|---|---|
| FFmpeg `lut3d` | Apply exported `.cube` to chart + demo clip | No error, colors sane, matches in-app preview |
| DaVinci Resolve (free) | Import `.cube` into LUT folder, apply to same clip | Visual match to preview; screenshot for deck |
| Premiere Pro | Section 10.3 | Same frame exported, DeltaE vs FFmpeg result reported |
| Mobile (stretch, optional photo app that imports `.cube`) | Apply to a still | Screenshot only, no numeric claim |

### 10.3 Premiere Pro via MCP

Premiere Pro MCP servers exist that expose project/timeline control (open project, import media, apply effects/LUTs, export frames) to an agent. Plan it as an automated acceptance test, not a runtime dependency:

1. Before the hackathon: install and smoke-test the chosen Premiere MCP on the demo machine with a trivial project. If it is flaky, drop to the manual checklist immediately and lose nothing.
2. Scripted test: create/open test project, import source clip, apply generated `.cube` as a Lumetri/LUT input, export a still at a fixed timecode, hand the still to the Python metrics script.
3. Compare Premiere still vs FFmpeg `lut3d` still: mean DeltaE2000 target under 2.0 on chart patches; investigate tetrahedral vs trilinear and input-range interpretation if it fails (Premiere LUT input range and normalization settings are the usual culprits).
4. Keep the exported Premiere still and the MCP session log as demo evidence: "the same file, inside Premiere, no plugin of ours installed."

Caveat to state in the pitch if asked: MCP control is a testing harness; end users just import the `.cube` normally.

### 10.4 Temporal stability proof

Grade a 5 second clip, compute per-frame mean color of a static region across frames for ChromaInvert output vs (optionally) any per-frame method screenshot for contrast. The LUT result is constant by construction; one slide with "frame-to-frame DeltaE: 0.00 by construction" is a strong judging moment.

---

## 11. Metrics and Targets (Definition of Done)

| Metric | Target | How measured |
|---|---|---|
| Synthetic recovery | Recovered LUT beats identity baseline by at least 40 percent mean DeltaE2000 reduction on held-out frames; absolute mean DeltaE vs ground-truth grade under 3.0 | `benchmark.py` |
| Optimization time | Under 10 s GPU (target 2 to 5 s), under 60 s CPU degraded mode | `report.json` |
| `.cube` validity | Loads in FFmpeg, Resolve, Premiere with zero errors | Section 10.2 matrix |
| Cross-tool agreement | Premiere vs FFmpeg still, chart mean DeltaE under 2.0 | Section 10.3 |
| Smoothness | No visible banding on a gradient ramp test image; max lattice neighbor delta reported | ramp image + report stats |
| Skin protection | Skin-masked mean hue shift within agreed tolerance vs unanchored run on demo footage | masks + report |
| End-to-end demo | Click Match to graded preview under 30 s total on demo machine | rehearsal timing |

If a target is missed, the number still goes in the README. Measured honesty beats adjectives in judging.

---

## 12. Team Division and Workflow

### 12.1 Roles

- Python/Color (Role 1): engine, losses, color profiles, spline, benchmark, `.cube` export, metrics script for Premiere stills. Owns Sections 6, 7, 9, 11 numbers.
- C++/App (Role 2): app shell, FFmpeg pipeline, job runner, preview/scopes, packaging. Owns Sections 8 and the demo machine.
- Floating/everyone: test assets and licenses, README, slides, demo rehearsal, Premiere/Resolve validation sessions. If a third or fourth member exists, give them validation plus demo assets full-time; it is the highest-leverage non-coding role.

### 12.2 Working agreements

- Freeze `job.json`/JSONL contract (Section 4.1) in hour 1. Changes need both devs in the room and a version bump in the file (`"contract_version": 1`).
- Each dev develops against canned inputs: Role 2 gets a fake engine script that emits progress and copies a known `.cube`; Role 1 gets checked-in sample frames. Nobody blocks on the other.
- Merge to `main` only when the vertical slice still runs. Short branches, small commits, commit messages that name the pipeline stage.
- One shared "demo health" checklist run at every milestone: CLI job, GUI job, FFmpeg apply, one external tool.

### 12.3 Repository structure (top level)

```
ChromaInvert/
  README.md                 # pitch, quickstart, results table, demo script pointer
  docs/
    CHROMAINVERT_HACKATHON_PLAN.md   # this file
    DEMO_SCRIPT.md          # 3 minute run-of-show, fallback lines
    ARCHITECTURE.md         # contract + color pipeline diagrams (extract from plan)
  engine/                   # Section 6.1
  app/                      # Section 8.2
  assets/                   # sample clips/frames, known LUTs, test chart (with sources)
  scripts/                  # benchmark, premiere-still metrics, package/demo launchers
  work/                     # gitignored runtime workdir
```

---

## 13. Timeline (36 Hour Assumption)

| Time | Python/Color | C++/App | Joint gate |
|---|---|---|---|
| H0 to H2 | Env, deps pinned, `.cube` writer, identity test | Toolchain decision, CMake skeleton, ffmpeg/ffprobe check | Contract frozen; identity LUT round-trips through FFmpeg |
| H2 to H6 | DifferentiableLUT3D + distribution loss on benchmark | Subprocess FFmpeg extract + `lut3d` preview, app skeleton | Benchmark v0 numbers printed |
| H6 to H12 | TV loss, masks v1, coarse-to-fine spline | JobRunner + JSONL progress, before/after UI | MVP gate: click to graded preview works |
| H12 to H18 | Log profile (S-Log3), tuning on real footage, CPU fallback | Scopes v1, metadata display, error dialogs | Real footage demo run; freeze feature list |
| H18 to H24 | Skin/shadow anchor tuning, benchmark final numbers | Premiere MCP test + Resolve check, packaging | External-tool matrix green or documented |
| H24 to H30 | Stretch only if gates green (1D pre-curves) | Preview polish, demo machine freeze | Full rehearsal 1, record backup video |
| H30 to H36 | Bugfix only | Slides, README results, rehearsal 2 and 3 | Recorded backup demo exists; no new features after H32 |

Hard rules: feature freeze at H32; the last 4 hours are rehearsal, packaging, and sleep rotation. Record a full backup demo video by H30 in case live hardware fails.

---

## 14. Scaling the Plan

- 24 hours: cut Target scopes to histograms only, one log profile, Premiere validation manual-only, coarse 17 LUT exported directly (spline upsample kept, it is cheap), no Linux claim.
- 48 hours: add second log profile, 1D pre-curves, tetrahedral fine-tune check, Linux build verification, batch mode.
- 3 to 4 people: third owns validation/demo assets (Section 10) and the metrics dashboard; fourth owns scopes and preview polish. Do not split the engine between two people mid-hackathon; the loss stack is one brain's job.

---

## 15. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Distribution matching produces plausible histogram, ugly image | Demo failure | Identity init, TV loss, anchor losses, synthetic benchmark gate before UI work, strength slider to back off live |
| Unseen colors map wildly (e.g. saturated blue sky) | Visible artifacts | Coarse lattice + spline smoothing, identity prior, gradient-ramp test image in every rehearsal |
| `.cube` axis order wrong (R/B swapped) | Grade looks inverted, confusing debugging | Golden pipeline test (Section 10.1) from hour 2 onward |
| Range/transfer misread (limited vs full, log tagged as 709) | Washed or crushed result | Metadata display, manual profile override, chart test per profile |
| Venue network down, weights/models unavailable | Segmentation stretch dies | Pre-download everything; heuristic masks are the shipping path anyway |
| GPU absent on demo machine | Slow optimization | CPU degraded mode with fewer pixels/iterations, progress UI, precomputed fallback result for the exact demo assets |
| Premiere MCP flaky or version mismatch | Validation story blocked | It is a test harness only; manual Premiere checklist and exported still achieve the same evidence |
| Qt/vcpkg build eats the event | No GUI | CLI pipeline plus simple ImGui or even a static HTML result page as demo surface; keep CLI golden from hour 6 |
| Scope creep (per-shot, HDR, training ideas) | Nothing finishes | Section 1.3 non-goals; stretch list requires MVP+Target gates green |

---

## 16. Demo Script Outline (3 Minutes)

1. Problem (20 s): hand-grading is slow; per-frame AI flickers. Show 2 s flicker example if available, else state it with the temporal-stability slide.
2. Live run (60 s): pick log clip + famous-look reference frame, click Match, narrate progress: frames sampled, lattice optimizing, loss falling. Show before/after wipe and scopes converging.
3. Portability proof (45 s): open the exported `.cube` result in Premiere (pre-opened project or MCP-exported still) and Resolve screenshot; stress "no plugin, no per-frame AI, same file".
4. Numbers (30 s): benchmark recovery DeltaE, seconds to optimize, frame-to-frame stability 0.00 by construction, skin-anchor before/after crop.
5. Close (25 s): who it is for (creators, mobile shooters, small post houses), roadmap: per-shot LUTs, ACES/HDR pipeline, embedded engine.

Rehearse failure lines too: if live optimization stalls, switch to the recorded run and the precomputed `.cube` for the same assets without apologizing at length.

---

## 17. Pre-Hackathon Checklist (Do This Week)

- [ ] Both devs: clone repo, build hello-world on the actual demo laptop (CMake+vcpkg or Qt; Python venv with CUDA PyTorch verified with `torch.cuda.is_available()`).
- [ ] Download and cache: PyTorch wheels, `colour-science`, any segmentation weights, FFmpeg build. Assume no venue downloads.
- [ ] Collect legal demo assets: one log clip the team shot or has rights to, 3 reference frames, a color chart shot, one known `.cube` for the benchmark. Note sources in `assets/SOURCES.md`.
- [ ] Smoke-test the Premiere Pro MCP on the demo machine, or decide manual-only now.
- [ ] Agree the toolchain decision (Section 8.1) and the contract (Section 4.1) before the clock starts.
- [ ] Create the repo skeleton (Section 12.3) with gitignored `work/`, CI optional and only if it costs under 30 minutes.

---

## 18. Open Questions to Resolve at Kickoff

1. Hackathon duration and team size: confirm, then apply Section 14 cuts/additions explicitly.
2. Demo footage: which camera/log format do we actually have? That picks the Tier 2 profile.
3. Demo machine GPU: model and VRAM decide iteration/pixel budgets and whether 33-direct optimization is viable.
4. GUI framework: has either dev shipped Qt or ImGui recently? Pick per Section 8.1 and freeze.
5. Judging criteria: weight of technical depth vs product polish decides whether H18 to H24 goes to Premiere validation or to scopes/preview polish.
