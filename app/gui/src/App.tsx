import { useEffect, useState } from "react";
import { getBridge } from "./api";
import { RunPhase } from "./types";

export default function App(): JSX.Element {
  const [sourceFrames, setSourceFrames] = useState<string>("");
  const [referenceFrames, setReferenceFrames] = useState<string>("");
  const [outputCube, setOutputCube] = useState<string>("work/out.cube");
  const [strength, setStrength] = useState<number>(1.0);
  const [phase, setPhase] = useState<RunPhase>(RunPhase.Idle);
  const [percent, setPercent] = useState<number>(0);
  const [status, setStatus] = useState<string>("Idle");
  const [log, setLog] = useState<string>("");

  useEffect(() => {
    const bridge = getBridge();
    if (bridge === null) {
      return;
    }
    bridge.onProgress((update) => {
      setPercent(update.percent);
      setStatus("Loss " + update.loss.toFixed(4));
    });
    bridge.onLog((line) => {
      setLog((prev) => (prev + line + "\n").slice(-8000));
    });
  }, []);

  const onMatch = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setStatus("Preload bridge missing: run under Electron.");
      return;
    }
    setPhase(RunPhase.Running);
    setPercent(0);
    setStatus("Running");
    bridge
      .runJob({ sourceFrames, referenceFrames, outputCube, strength, lutSize: 33, device: "auto" })
      .then((result) => {
        setPhase(result.exitCode === 0 ? RunPhase.Done : RunPhase.Failed);
        setStatus(result.summary);
      });
  };

  const onCancel = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      return;
    }
    bridge.cancelJob().then(() => {
      setPhase(RunPhase.Idle);
      setStatus("Cancelled");
    });
  };

  return (
    <main>
      <h1>ChromaInvert</h1>
      <label>Source frames <input value={sourceFrames} onChange={(e) => setSourceFrames(e.target.value)} /></label>
      <label>Reference frames <input value={referenceFrames} onChange={(e) => setReferenceFrames(e.target.value)} /></label>
      <label>Output cube <input value={outputCube} onChange={(e) => setOutputCube(e.target.value)} /></label>
      <label>Strength <input type="number" step="0.05" value={strength} onChange={(e) => setStrength(Number(e.target.value))} /></label>
      <div>
        <button onClick={onMatch} disabled={phase === RunPhase.Running}>Match</button>
        <button onClick={onCancel} disabled={phase !== RunPhase.Running}>Cancel</button>
      </div>
      <progress value={percent} max={100} />
      <p>{status}</p>
      <pre>{log}</pre>
    </main>
  );
}
