import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { getBridge, isDesktop } from "./api";
import type { JobConfig } from "./types";
import { RunPhase } from "./types";

interface FrameListProps {
  title: string;
  files: string[];
  disabled: boolean;
  hint: string;
  manualValue: string;
  onManualChange: (value: string) => void;
  onManualAdd: () => void;
  onBrowse: () => void;
  onClear: () => void;
  onRemove: (index: number) => void;
}

function FrameList(props: FrameListProps): JSX.Element {
  return (
    <div className="field">
      <span>
        {props.title} ({props.files.length})
      </span>
      <span className="hint">{props.hint}</span>
      <div className="row">
        <button type="button" onClick={props.onBrowse} disabled={props.disabled}>
          Browse files
        </button>
        <button type="button" className="ghost" onClick={props.onClear} disabled={props.disabled || props.files.length === 0}>
          Clear
        </button>
      </div>
      {props.files.length === 0 ? (
        <div className="empty">No files selected yet.</div>
      ) : (
        <ul className="file-list">
          {props.files.map((file, index) => (
            <li className="file-item" key={file + index}>
              <code title={file}>{file}</code>
              <button type="button" onClick={() => props.onRemove(index)} disabled={props.disabled}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="row">
        <input
          className="grow"
          type="text"
          placeholder="Or paste a file path and press Add"
          aria-label={props.title + " manual path"}
          value={props.manualValue}
          disabled={props.disabled}
          onChange={(e: ChangeEvent<HTMLInputElement>) => props.onManualChange(e.target.value)}
        />
        <button type="button" onClick={props.onManualAdd} disabled={props.disabled}>
          Add
        </button>
      </div>
    </div>
  );
}

function dedupeAppend(current: string[], incoming: string[]): string[] {
  const seen = new Set(current);
  const next = current.slice();
  for (const item of incoming) {
    const trimmed = item.trim();
    if (trimmed !== "" && !seen.has(trimmed)) {
      seen.add(trimmed);
      next.push(trimmed);
    }
  }
  return next;
}

function badgeClass(phase: RunPhase): string {
  if (phase === RunPhase.Running) {
    return "badge running";
  }
  if (phase === RunPhase.Done) {
    return "badge done";
  }
  if (phase === RunPhase.Failed) {
    return "badge failed";
  }
  return "badge";
}

function badgeLabel(phase: RunPhase): string {
  if (phase === RunPhase.Running) {
    return "Running";
  }
  if (phase === RunPhase.Done) {
    return "Done";
  }
  if (phase === RunPhase.Failed) {
    return "Failed";
  }
  return "Idle";
}

export default function App(): JSX.Element {
  const [sourceFrames, setSourceFrames] = useState<string[]>([]);
  const [referenceFrames, setReferenceFrames] = useState<string[]>([]);
  const [referenceOnly, setReferenceOnly] = useState<boolean>(false);
  const [customWeights, setCustomWeights] = useState<string>("");
  const [sourceManual, setSourceManual] = useState<string>("");
  const [referenceManual, setReferenceManual] = useState<string>("");
  const [outputCube, setOutputCube] = useState<string>("work/out.cube");
  const [inputProfile, setInputProfile] = useState<string>("rec709");
  const [strength, setStrength] = useState<number>(1.0);
  const [lutSize, setLutSize] = useState<number>(33);
  const [coarseSize, setCoarseSize] = useState<number>(17);
  const [iterations, setIterations] = useState<number>(400);
  const [fineIterations, setFineIterations] = useState<number>(30);
  const [seed, setSeed] = useState<number>(42);
  const [device, setDevice] = useState<string>("auto");
  const [deterministic, setDeterministic] = useState<boolean>(false);
  const [phase, setPhase] = useState<RunPhase>(RunPhase.Idle);
  const [percent, setPercent] = useState<number>(0);
  const [loss, setLoss] = useState<number>(0);
  const [iterText, setIterText] = useState<string>("");
  const [status, setStatus] = useState<string>("Idle. Pick frames, then press Match.");
  const [errors, setErrors] = useState<string[]>([]);
  const [log, setLog] = useState<string>("");
  const logRef = useRef<HTMLPreElement | null>(null);

  const running = phase === RunPhase.Running;
  const desktop = isDesktop();
  const contractVersion = inputProfile.indexOf("slog3") === 0 ? 2 : 1;
  const footageDone =
    (referenceOnly || sourceFrames.length > 0) && referenceFrames.length > 0;
  const outputDone = outputCube.trim().toLowerCase().endsWith(".cube");
  const settingsValid =
    Number.isFinite(strength) &&
    strength >= 0 &&
    strength <= 1 &&
    Number.isInteger(lutSize) &&
    lutSize >= 2 &&
    Number.isInteger(coarseSize) &&
    coarseSize >= 2 &&
    Number.isInteger(iterations) &&
    iterations >= 0 &&
    Number.isInteger(fineIterations) &&
    fineIterations >= 0 &&
    iterations + fineIterations > 0 &&
    Number.isInteger(seed);
  const stepsDone = [footageDone, outputDone, settingsValid, phase === RunPhase.Done];
  const activeStep =
    phase === RunPhase.Running || phase === RunPhase.Failed || phase === RunPhase.Done
      ? 3
      : !stepsDone[0]
        ? 0
        : !stepsDone[1]
          ? 1
          : !stepsDone[2]
            ? 2
            : 3;
  const stepNames = ["Footage", "Output", "Settings", "Run"];

  useEffect(() => {
    const bridge = getBridge();
    if (bridge === null) {
      return;
    }
    bridge.onProgress((update) => {
      setPercent(update.percent);
      setLoss(update.loss);
      setIterText("iter " + update.iter + "/" + update.iters);
      setStatus("Optimizing: " + update.percent + "% (loss " + update.loss.toFixed(4) + ")");
    });
    bridge.onLog((line) => {
      setLog((prev) => (prev + line + "\n").slice(-12000));
    });
  }, []);

  useEffect(() => {
    const el = logRef.current;
    if (el !== null) {
      el.scrollTop = el.scrollHeight;
    }
  }, [log]);

  function collectErrors(): string[] {
    const found: string[] = [];
    if (!referenceOnly && sourceFrames.length === 0) {
      found.push("Add at least one source frame, or enable reference-only mode.");
    }
    if (referenceFrames.length === 0) {
      found.push("Add at least one reference frame.");
    }
    if (outputCube.trim() === "") {
      found.push("Pick an output .cube path.");
    } else if (!outputCube.trim().toLowerCase().endsWith(".cube")) {
      found.push("Output path must end with .cube.");
    }
    if (!Number.isFinite(strength) || strength < 0 || strength > 1) {
      found.push("Strength must be a number between 0 and 1.");
    }
    if (!Number.isInteger(lutSize) || lutSize < 2) {
      found.push("LUT size must be an integer of at least 2 (17 or 33 typical).");
    }
    if (!Number.isInteger(coarseSize) || coarseSize < 2) {
      found.push("Coarse size must be an integer of at least 2.");
    }
    if (!Number.isInteger(iterations) || iterations < 0) {
      found.push("Iterations must be a whole number of 0 or more.");
    }
    if (!Number.isInteger(fineIterations) || fineIterations < 0) {
      found.push("Fine iterations must be a whole number of 0 or more.");
    }
    if (iterations + fineIterations === 0) {
      found.push("At least one optimization stage must run (iterations + fine iterations > 0).");
    }
    if (!Number.isInteger(seed)) {
      found.push("Seed must be a whole number.");
    }
    return found;
  }

  function toJobConfig(): JobConfig {
    return {
      sourceFrames,
      referenceFrames,
      referenceOnly,
      customWeights: customWeights.trim(),
      outputCube: outputCube.trim(),
      inputProfile,
      strength,
      lutSize,
      coarseSize,
      iterations,
      fineIterations,
      seed,
      device,
      deterministic
    };
  }

  const onBrowseSources = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setStatus("File dialogs need the Electron app. Paste a path below instead.");
      return;
    }
    bridge.pickSourceFrames().then(
      (picked) => {
        if (picked.length > 0) {
          setSourceFrames((prev) => dedupeAppend(prev, picked));
        }
      },
      () => {
        setStatus("Source file dialog was unavailable.");
      }
    );
  };

  const onBrowseReferences = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setStatus("File dialogs need the Electron app. Paste a path below instead.");
      return;
    }
    bridge.pickReferenceFrames().then(
      (picked) => {
        if (picked.length > 0) {
          setReferenceFrames((prev) => dedupeAppend(prev, picked));
        }
      },
      () => {
        setStatus("Reference file dialog was unavailable.");
      }
    );
  };

  const onBrowseWeights = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setStatus("File dialogs need the Electron app. Type the weights path instead.");
      return;
    }
    bridge.pickWeights().then(
      (picked) => {
        if (picked !== null && picked !== "") {
          setCustomWeights(picked);
        }
      },
      () => {
        setStatus("Weights file dialog was unavailable.");
      }
    );
  };

  const onBrowseOutput = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setStatus("File dialogs need the Electron app. Type the output path instead.");
      return;
    }
    bridge.pickOutputCube(outputCube).then(
      (picked) => {
        if (picked !== null && picked !== "") {
          setOutputCube(picked);
        }
      },
      () => {
        setStatus("Output file dialog was unavailable.");
      }
    );
  };

  const onMatch = (): void => {
    const found = collectErrors();
    setErrors(found);
    if (found.length > 0) {
      setStatus("Fix the highlighted issues, then press Match.");
      return;
    }
    const bridge = getBridge();
    if (bridge === null) {
      setStatus("Run under Electron to start the engine. Inputs validate cleanly.");
      return;
    }
    setPhase(RunPhase.Running);
    setPercent(0);
    setLoss(0);
    setIterText("");
    setStatus("Running: writing job.json and starting the engine.");
    bridge.runJob(toJobConfig()).then(
      (result) => {
        setPhase(result.exitCode === 0 ? RunPhase.Done : RunPhase.Failed);
        setStatus(result.summary);
        if (result.exitCode === 0) {
          setPercent(100);
        }
      },
      () => {
        setPhase(RunPhase.Failed);
        setStatus("Failed: engine call was rejected. See the log.");
      }
    );
  };

  const onCancel = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      return;
    }
    bridge.cancelJob().then(
      () => {
        setPhase(RunPhase.Idle);
        setStatus("Cancelled.");
      },
      () => {
        setStatus("Cancel request was unavailable.");
      }
    );
  };

  return (
    <div className="app">
      <header className="header">
        <h1>ChromaInvert</h1>
        <p>
          Match the grade of a reference frame onto source footage, then export a smooth industry
          standard .cube. Contract v{contractVersion} job, stdout JSONL progress, report.json summary.
        </p>
        {!desktop && (
          <div className="notice">
            Running in a browser preview: file dialogs and Match need the Electron app. Manual paths
            still validate here.
          </div>
        )}
      </header>

      <ol className="steps" aria-label="Workflow progress">
        {stepNames.map((name, index) => (
          <li
            key={name}
            className={"step" + (stepsDone[index] ? " done" : index === activeStep ? " active" : "")}
            aria-current={index === activeStep ? "step" : undefined}
          >
            <span className="step-num" aria-hidden="true">
              {index + 1}
            </span>
            {name}
          </li>
        ))}
      </ol>

      <div className="layout">
        <div className="column">
          <section className="card" aria-label="Footage">
            <h2>
              <span className="step-num" aria-hidden="true">
                1
              </span>
              Footage
            </h2>
            <p className="hint">TIFF preferred for precision. PNG, BMP, and JPG also load.</p>
            <FrameList
              title="Source frames"
              files={sourceFrames}
              disabled={running || referenceOnly}
              hint={referenceOnly ? "Skipped in reference-only mode." : "Ungraded footage to match."}
              manualValue={sourceManual}
              onManualChange={setSourceManual}
              onManualAdd={() => {
                if (sourceManual.trim() !== "") {
                  setSourceFrames((prev) => dedupeAppend(prev, [sourceManual]));
                  setSourceManual("");
                }
              }}
              onBrowse={onBrowseSources}
              onClear={() => setSourceFrames([])}
              onRemove={(index) => setSourceFrames((prev) => prev.filter((_, i) => i !== index))}
            />
            <FrameList
              title="Reference frames"
              files={referenceFrames}
              disabled={running}
              hint="Graded look to copy."
              manualValue={referenceManual}
              onManualChange={setReferenceManual}
              onManualAdd={() => {
                if (referenceManual.trim() !== "") {
                  setReferenceFrames((prev) => dedupeAppend(prev, [referenceManual]));
                  setReferenceManual("");
                }
              }}
              onBrowse={onBrowseReferences}
              onClear={() => setReferenceFrames([])}
              onRemove={(index) => setReferenceFrames((prev) => prev.filter((_, i) => i !== index))}
            />
          </section>

          <section className="card" aria-label="Output">
            <h2>
              <span className="step-num" aria-hidden="true">
                2
              </span>
              Output
            </h2>
            <p className="hint">job.json and report.json land next to this path.</p>
            <div className="field">
              <span>Output .cube</span>
              <div className="row">
                <input
                  className="grow"
                  type="text"
                  value={outputCube}
                  aria-label="Output cube path"
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setOutputCube(e.target.value)}
                />
                <button type="button" onClick={onBrowseOutput} disabled={running}>
                  Browse
                </button>
              </div>
            </div>
          </section>

          <section className="card" aria-label="Grade settings">
            <h2>
              <span className="step-num" aria-hidden="true">
                3
              </span>
              Grade settings
            </h2>
            <p className="hint">Profile decodes both sides. Strength blends back toward identity.</p>
            <label className="check">
              <input
                type="checkbox"
                checked={referenceOnly}
                disabled={running}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setReferenceOnly(e.target.checked)}
              />
              Reference-only: recover the look from graded frames alone (no source needed)
            </label>
            {referenceOnly && (
              <div className="field">
                <span>Predictor weights (.pt you trained)</span>
                <div className="row">
                  <input
                    className="grow"
                    type="text"
                    value={customWeights}
                    aria-label="Custom weights path"
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setCustomWeights(e.target.value)}
                  />
                  <button type="button" onClick={onBrowseWeights} disabled={running}>
                    Browse
                  </button>
                </div>
              </div>
            )}
            <div className="grid2">
              <label className="field">
                <span>Input profile</span>
                <select
                  value={inputProfile}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setInputProfile(e.target.value)}
                >
                  <option value="rec709">rec709</option>
                  <option value="rec2020">rec2020</option>
                  <option value="apple_log">apple_log</option>
                  <option value="slog3">slog3</option>
                  <option value="slog3_sgamut3cine">slog3_sgamut3cine</option>
                </select>
              </label>
              <label className="field">
                <span>Device</span>
                <select
                  value={device}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setDevice(e.target.value)}
                >
                  <option value="auto">auto</option>
                  <option value="cuda">cuda</option>
                  <option value="cpu">cpu</option>
                </select>
              </label>
            </div>
            <div className="grid2">
              <label className="field">
                <span>Strength ({strength.toFixed(2)})</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={strength}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setStrength(Number(e.target.value))}
                />
              </label>
              <label className="field">
                <span>LUT size</span>
                <select
                  value={String(lutSize)}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setLutSize(Number(e.target.value))}
                >
                  <option value="17">17</option>
                  <option value="33">33</option>
                </select>
              </label>
            </div>
            <details className="advanced">
              <summary>Advanced tuning</summary>
              <div className="grid2">
                <label className="field">
                  <span>Iterations</span>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={iterations}
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setIterations(Number(e.target.value))
                    }
                  />
                </label>
                <label className="field">
                  <span>Fine iterations</span>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={fineIterations}
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setFineIterations(Number(e.target.value))
                    }
                  />
                </label>
              </div>
              <div className="grid2">
                <label className="field">
                  <span>Coarse size</span>
                  <input
                    type="number"
                    min={2}
                    step={1}
                    value={coarseSize}
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setCoarseSize(Number(e.target.value))
                    }
                  />
                </label>
                <label className="field">
                  <span>Seed</span>
                  <input
                    type="number"
                    step={1}
                    value={seed}
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setSeed(Number(e.target.value))}
                  />
                </label>
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={deterministic}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setDeterministic(e.target.checked)}
                />
                Deterministic GPU mode (slower, best effort reproducibility)
              </label>
            </details>
          </section>
        </div>

        <div className="column">
          <section className="card" aria-label="Run">
            <h2>
              <span className="step-num" aria-hidden="true">
                4
              </span>
              Run
            </h2>
            <p className="hint">
              {referenceOnly ? "reference-only" : sourceFrames.length + " source,"} {referenceFrames.length}{" "}
              reference, contract v{contractVersion}, {device}, LUT {lutSize}.
            </p>
            {errors.length > 0 && (
              <div className="errors" role="alert">
                <strong>Check these fields:</strong>
                <ul>
                  {errors.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="row" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="primary"
                onClick={onMatch}
                disabled={running}
                aria-busy={running}
              >
                {running ? "Matching..." : "Match"}
              </button>
              <button type="button" onClick={onCancel} disabled={!running}>
                Cancel
              </button>
            </div>
            <div className="progress-wrap" style={{ marginTop: 12 }}>
              <progress value={percent} max={100} aria-label="Optimization progress" />
              <div className="progress-meta">
                {percent}% {iterText === "" ? "" : ": " + iterText} (loss {loss.toFixed(4)})
              </div>
            </div>
            <div className="status" style={{ marginTop: 8 }} role="status">
              <span className={badgeClass(phase)}>{badgeLabel(phase)}</span>
              <span>{status}</span>
            </div>
          </section>

          <section className="card">
            <h2>Log</h2>
            <p className="hint">Engine stdout tail plus stderr lines.</p>
            <div className="row" style={{ marginBottom: 8 }}>
              <button type="button" className="ghost" onClick={() => setLog("")}>
                Clear log
              </button>
            </div>
            <pre className="log" ref={logRef} aria-label="Engine log" tabIndex={0}>
              {log === "" ? "No output yet." : log}
            </pre>
            <div className="footer">Preview encode and scopes arrive with the FFmpeg link.</div>
          </section>
        </div>
      </div>
    </div>
  );
}
