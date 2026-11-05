import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { getBridge, isDesktop } from "./api";
import type { JobConfig, VideoProbe } from "./types";
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

function toFileUrl(path: string): string {
  return "file:///" + encodeURI(path.replace(/\\/g, "/")).replace(/#/g, "%23");
}

function formatSeconds(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return "unknown";
  }
  return value.toFixed(2) + "s";
}

function dirOfCube(cubePath: string): string {
  const trimmed = cubePath.trim();
  const cut = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
  const dir = cut <= 0 ? "" : trimmed.slice(0, cut);
  return dir === "" ? "work" : dir;
}

function probeDuration(probe: VideoProbe | null): number {
  if (probe === null || probe.error !== "") {
    return -1;
  }
  return probe.duration;
}

function defaultReferenceProfile(profile: string): string {
  if (profile === "apple_log" || profile.indexOf("slog3") === 0) {
    return "rec709";
  }
  return profile;
}

function isLogProfile(profile: string): boolean {
  return profile === "apple_log" || profile.indexOf("slog3") === 0;
}

function canonicalProfile(profile: string): string {
  if (profile === "apple_log") {
    return "apple_log";
  }
  if (profile.indexOf("slog3") === 0) {
    return "slog3";
  }
  return profile;
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
  const [referenceProfile, setReferenceProfile] = useState<string>("auto");
  const [weightTv, setWeightTv] = useState<number>(0.1);
  const [weightShadow, setWeightShadow] = useState<number>(0.25);
  const [alignedPairs, setAlignedPairs] = useState<boolean>(false);
  const [premiereStills, setPremiereStills] = useState<boolean>(false);
  const [premiereExport, setPremiereExport] = useState<boolean>(true);
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
  const [sourceVideo, setSourceVideo] = useState<string>("");
  const [referenceVideo, setReferenceVideo] = useState<string>("");
  const [sourceProbe, setSourceProbe] = useState<VideoProbe | null>(null);
  const [referenceProbe, setReferenceProbe] = useState<VideoProbe | null>(null);
  const [sourceTime, setSourceTime] = useState<number>(0);
  const [referenceTime, setReferenceTime] = useState<number>(0);
  const [lockTimes, setLockTimes] = useState<boolean>(true);
  const [grabbing, setGrabbing] = useState<string>("");
  const [videoNote, setVideoNote] = useState<string>("");
  const sourceVidRef = useRef<HTMLVideoElement | null>(null);
  const referenceVidRef = useRef<HTMLVideoElement | null>(null);

  const running = phase === RunPhase.Running;
  const desktop = isDesktop();
  const sourceDur = probeDuration(sourceProbe);
  const refDur = probeDuration(referenceProbe);
  const lengthDelta = sourceDur > 0 && refDur > 0 ? Math.abs(sourceDur - refDur) : -1;
  const lengthsMatch = lengthDelta >= 0 && lengthDelta <= 0.5;
  const contractVersion = inputProfile.indexOf("slog3") === 0 ? 2 : 1;
  const resolvedReference = referenceProfile === "auto" ? defaultReferenceProfile(inputProfile) : referenceProfile;
  const footageDone =
    (referenceOnly || sourceFrames.length > 0) && referenceFrames.length > 0;
  const outputDone = outputCube.trim().toLowerCase().endsWith(".cube");
  const settingsValid =
    Number.isFinite(strength) &&
    strength >= 0 &&
    strength <= 1 &&
    (referenceProfile === "auto" ||
      referenceProfile === "rec709" ||
      referenceProfile === "rec2020" ||
      referenceProfile === "apple_log" ||
      referenceProfile === "slog3" ||
      referenceProfile === "slog3_sgamut3cine") &&
    Number.isFinite(weightTv) &&
    weightTv >= 0 &&
    Number.isFinite(weightShadow) &&
    weightShadow >= 0 &&
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
    if (premiereStills && sourceFrames.some((p) => /video_frames[\\/]source_/.test(p))) {
      found.push(
        "Premiere stills needs source frames exported from Premiere; frames captured from a video here are raw footage. Untick Premiere stills and set the input profile to apple_log for Apple Log footage."
      );
    }
    if (outputCube.trim() === "") {
      found.push("Pick an output .cube path.");
    } else if (!outputCube.trim().toLowerCase().endsWith(".cube")) {
      found.push("Output path must end with .cube.");
    }
    if (!Number.isFinite(strength) || strength < 0 || strength > 1) {
      found.push("Strength must be a number between 0 and 1.");
    }
    if (
      referenceProfile !== "auto" &&
      referenceProfile !== "rec709" &&
      referenceProfile !== "rec2020" &&
      referenceProfile !== "apple_log" &&
      referenceProfile !== "slog3" &&
      referenceProfile !== "slog3_sgamut3cine"
    ) {
      found.push("Reference profile must be Auto, rec709, rec2020, apple_log, slog3, or slog3_sgamut3cine.");
    }
    if (isLogProfile(referenceProfile) && canonicalProfile(referenceProfile) !== canonicalProfile(inputProfile)) {
      found.push("Reference profile is a log profile: graded references must use a display profile such as rec709.");
    }
    if (!Number.isFinite(weightTv) || weightTv < 0) {
      found.push("Smoothness weight must be a number of 0 or more.");
    }
    if (!Number.isFinite(weightShadow) || weightShadow < 0) {
      found.push("Shadow weight must be a number of 0 or more.");
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

  // Paired fits need a longer, less regularized run to reach the grade; measured on Premiere stills.
  function applyPairedPreset(on: boolean): void {
    setAlignedPairs(on);
    setIterations(on ? 1500 : 400);
    setFineIterations(on ? 200 : 30);
    setWeightTv(on ? 0.03 : 0.1);
    setWeightShadow(on ? 0.05 : 0.25);
  }

  function applyPremiereStills(on: boolean): void {
    setPremiereStills(on);
    if (on) {
      setInputProfile("rec709");
      setReferenceProfile("auto");
      applyPairedPreset(true);
    }
  }

  function toJobConfig(): JobConfig {
    return {
      sourceFrames,
      referenceFrames,
      referenceOnly,
      customWeights: customWeights.trim(),
      outputCube: outputCube.trim(),
      inputProfile,
      referenceProfile,
      weightTv,
      weightShadow,
      weightPaired: alignedPairs ? 50 : 0,
      premiereExport: inputProfile === "apple_log" && premiereExport,
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

  const refreshProbe = (kind: string, videoPath: string): void => {
    const bridge = getBridge();
    if (bridge === null || videoPath.trim() === "") {
      return;
    }
    bridge.probeVideo(videoPath).then(
      (probe) => {
        if (kind === "source") {
          setSourceProbe(probe);
          if (probe.error === "" && probe.duration > 0) {
            setSourceTime((prev) => Math.min(Math.max(prev, 0), probe.duration));
          }
        } else {
          setReferenceProbe(probe);
          if (probe.error === "" && probe.duration > 0) {
            setReferenceTime((prev) => Math.min(Math.max(prev, 0), probe.duration));
          }
        }
      },
      () => {
        const failed: VideoProbe = {
          path: videoPath,
          duration: -1,
          width: 0,
          height: 0,
          fps: "unknown",
          codec: "unknown",
          error: "Probe was unavailable."
        };
        if (kind === "source") {
          setSourceProbe(failed);
        } else {
          setReferenceProbe(failed);
        }
      }
    );
  };

  const onBrowseSourceVideo = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setVideoNote("Video import needs the Electron app.");
      return;
    }
    bridge.pickSourceVideo().then(
      (picked) => {
        if (picked !== null && picked !== "") {
          setSourceVideo(picked);
          setSourceProbe(null);
          refreshProbe("source", picked);
        }
      },
      () => {
        setVideoNote("Source video dialog was unavailable.");
      }
    );
  };

  const onBrowseReferenceVideo = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setVideoNote("Video import needs the Electron app.");
      return;
    }
    bridge.pickReferenceVideo().then(
      (picked) => {
        if (picked !== null && picked !== "") {
          setReferenceVideo(picked);
          setReferenceProbe(null);
          refreshProbe("reference", picked);
        }
      },
      () => {
        setVideoNote("Reference video dialog was unavailable.");
      }
    );
  };

  const onVideoSeek = (kind: string, value: number): void => {
    const safe = Number.isFinite(value) && value >= 0 ? value : 0;
    if (lockTimes) {
      const sourceDur = probeDuration(sourceProbe);
      const refDur = probeDuration(referenceProbe);
      setSourceTime(sourceDur > 0 ? Math.min(safe, sourceDur) : safe);
      setReferenceTime(refDur > 0 ? Math.min(safe, refDur) : safe);
      if (sourceVidRef.current !== null) {
        sourceVidRef.current.currentTime = sourceDur > 0 ? Math.min(safe, sourceDur) : safe;
      }
      if (referenceVidRef.current !== null) {
        referenceVidRef.current.currentTime = refDur > 0 ? Math.min(safe, refDur) : safe;
      }
      return;
    }
    if (kind === "source") {
      const dur = probeDuration(sourceProbe);
      const clamped = dur > 0 ? Math.min(safe, dur) : safe;
      setSourceTime(clamped);
      if (sourceVidRef.current !== null) {
        sourceVidRef.current.currentTime = clamped;
      }
    } else {
      const dur = probeDuration(referenceProbe);
      const clamped = dur > 0 ? Math.min(safe, dur) : safe;
      setReferenceTime(clamped);
      if (referenceVidRef.current !== null) {
        referenceVidRef.current.currentTime = clamped;
      }
    }
  };

  const captureFrame = (kind: string, atTime: number): void => {
    const bridge = getBridge();
    const videoPath = kind === "source" ? sourceVideo : referenceVideo;
    if (bridge === null) {
      setVideoNote("Frame capture needs the Electron app.");
      return;
    }
    if (videoPath.trim() === "") {
      setVideoNote("Pick a " + kind + " video first.");
      return;
    }
    setGrabbing(kind);
    setVideoNote("Grabbing " + kind + " frame at " + atTime.toFixed(2) + "s.");
    bridge.grabFrame(videoPath, atTime, kind, dirOfCube(outputCube)).then(
      (grab) => {
        setGrabbing("");
        if (grab.error !== "") {
          setVideoNote(kind + " capture failed: " + grab.error);
          return;
        }
        if (kind === "source") {
          setSourceFrames((prev) => dedupeAppend(prev, [grab.framePath]));
        } else {
          setReferenceFrames((prev) => dedupeAppend(prev, [grab.framePath]));
        }
        setVideoNote("Captured " + kind + " frame at " + grab.timestamp.toFixed(2) + "s.");
      },
      () => {
        setGrabbing("");
        setVideoNote(kind + " capture was unavailable.");
      }
    );
  };

  const captureBoth = (): void => {
    const bridge = getBridge();
    if (bridge === null) {
      setVideoNote("Frame capture needs the Electron app.");
      return;
    }
    if (sourceVideo.trim() === "" || referenceVideo.trim() === "") {
      setVideoNote("Pick both videos first.");
      return;
    }
    const at = refDur > 0 ? Math.min(sourceTime, refDur) : sourceTime;
    const clampedSource = sourceDur > 0 ? Math.min(at, sourceDur) : at;
    const outDir = dirOfCube(outputCube);
    setGrabbing("both");
    setVideoNote("Grabbing both frames at " + at.toFixed(2) + "s.");
    bridge.grabFrame(sourceVideo, clampedSource, "source", outDir).then(
      (src) => {
        if (src.error !== "") {
          setGrabbing("");
          setVideoNote("Source capture failed: " + src.error);
          return;
        }
        setSourceFrames((prev) => dedupeAppend(prev, [src.framePath]));
        bridge.grabFrame(referenceVideo, at, "reference", outDir).then(
          (ref) => {
            setGrabbing("");
            if (ref.error !== "") {
              setVideoNote("Reference capture failed: " + ref.error);
              return;
            }
            setReferenceFrames((prev) => dedupeAppend(prev, [ref.framePath]));
            setVideoNote("Captured both at " + at.toFixed(2) + "s.");
          },
          () => {
            setGrabbing("");
            setVideoNote("Reference capture was unavailable.");
          }
        );
      },
      () => {
        setGrabbing("");
        setVideoNote("Source capture was unavailable.");
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

  const renderVideoBlock = (kind: string): JSX.Element => {
    const isSource = kind === "source";
    const videoPath = isSource ? sourceVideo : referenceVideo;
    const probe = isSource ? sourceProbe : referenceProbe;
    const time = isSource ? sourceTime : referenceTime;
    const dur = isSource ? sourceDur : refDur;
    const vidRef = isSource ? sourceVidRef : referenceVidRef;
    const onBrowse = isSource ? onBrowseSourceVideo : onBrowseReferenceVideo;
    const onClear = (): void => {
      if (isSource) {
        setSourceVideo("");
        setSourceProbe(null);
      } else {
        setReferenceVideo("");
        setReferenceProbe(null);
      }
    };
    const meta =
      probe === null
        ? "No probe yet. Browse a file to read duration."
        : probe.error !== ""
          ? probe.error
          : probe.width + "x" + probe.height + " " + probe.codec + " " + probe.fps + " fps, " + formatSeconds(probe.duration);
    return (
      <div className="video-block">
        <span className="video-title">{isSource ? "Source video (ungraded)" : "Reference video (graded)"}</span>
        <div className="row">
          <button type="button" onClick={onBrowse} disabled={running}>
            Browse video
          </button>
          <button type="button" className="ghost" onClick={onClear} disabled={running || videoPath === ""}>
            Clear
          </button>
        </div>
        {videoPath === "" ? (
          <div className="empty">No video selected yet.</div>
        ) : (
          <div className="file-item">
            <code title={videoPath}>{videoPath}</code>
          </div>
        )}
        <div className="hint">{meta}</div>
        {videoPath !== "" && desktop && (
          <video
            key={videoPath}
            ref={vidRef}
            className="video-preview"
            src={toFileUrl(videoPath)}
            controls
            preload="metadata"
            onTimeUpdate={(e) => {
              if (!lockTimes) {
                if (isSource) {
                  setSourceTime(e.currentTarget.currentTime);
                } else {
                  setReferenceTime(e.currentTarget.currentTime);
                }
              }
            }}
          />
        )}
        <div className="row">
          <input
            className="grow"
            type="range"
            min={0}
            max={dur > 0 ? dur : 100}
            step={0.04}
            value={dur > 0 ? Math.min(time, dur) : time}
            aria-label={(isSource ? "Source" : "Reference") + " video timestamp"}
            disabled={running || videoPath === "" || dur <= 0}
            onChange={(e: ChangeEvent<HTMLInputElement>) => onVideoSeek(kind, Number(e.target.value))}
          />
          <input
            type="number"
            min={0}
            max={dur > 0 ? dur : undefined}
            step={0.1}
            value={Number(time.toFixed(2))}
            aria-label={(isSource ? "Source" : "Reference") + " timestamp seconds"}
            disabled={running || videoPath === ""}
            onChange={(e: ChangeEvent<HTMLInputElement>) => onVideoSeek(kind, Number(e.target.value))}
          />
        </div>
        <div className="row">
          <button
            type="button"
            onClick={() => captureFrame(kind, time)}
            disabled={running || grabbing !== "" || videoPath === ""}
          >
            {grabbing === kind ? "Grabbing..." : "Capture frame at " + time.toFixed(2) + "s"}
          </button>
        </div>
      </div>
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

          <section className="card" aria-label="Video import">
            <h2>Video import</h2>
            <p className="hint">
              Import the ungraded and graded videos, scrub to a frame, then capture it into the frame lists
              above. Captures land in video_frames next to the output cube.
            </p>
            {!desktop && (
              <div className="notice">
                Video preview and capture need the Electron app. Manual frame paths still validate here.
              </div>
            )}
            <div className="video-grid">
              {renderVideoBlock("source")}
              {renderVideoBlock("reference")}
            </div>
            <div className="field">
              <span>Length match</span>
              <span className="hint">
                Source {formatSeconds(sourceDur)}, reference {formatSeconds(refDur)}
                {lengthDelta >= 0 ? ", delta " + lengthDelta.toFixed(2) + "s" : ". Capture needs both durations."}
              </span>
              {lengthDelta >= 0 && (
                <span className={lengthsMatch ? "length-ok" : "length-warn"}>
                  {lengthsMatch ? "Lengths match." : "Lengths differ: captures still work, compare the same moment."}
                </span>
              )}
              <label className="check">
                <input
                  type="checkbox"
                  checked={lockTimes}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setLockTimes(e.target.checked)}
                />
                Lock timestamps (scrub and capture the same moment in both videos)
              </label>
              <div className="row">
                <button
                  type="button"
                  onClick={captureBoth}
                  disabled={running || grabbing !== "" || sourceVideo === "" || referenceVideo === ""}
                >
                  {grabbing !== "" ? "Grabbing..." : "Capture both at matched time"}
                </button>
              </div>
              {videoNote !== "" && <span className="hint">{videoNote}</span>}
            </div>
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
            <p className="hint">Source profile decodes source frames. Reference profile decodes the graded reference: keep Auto (rec709 for log sources such as Apple Log). Strength blends back toward identity.</p>
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
            <label className="check">
              <input
                type="checkbox"
                checked={premiereStills}
                disabled={running || referenceOnly}
                onChange={(e: ChangeEvent<HTMLInputElement>) => applyPremiereStills(e.target.checked)}
              />
              Premiere stills: source frames are exported from Premiere with no LUT and reference frames
              are the same times with your grade. The cube goes in Lumetri Input LUT. For raw Apple Log
              video captured here, leave this off and use apple_log instead.
            </label>
            {premiereStills && (
              <p className="hint">
                Premiere color-manages log clips before Lumetri, so the cube is trained on what Premiere
                renders: rec709 profile and same-frame pairs are set for you. Use File &gt; Export &gt;
                Frame on the ungraded clip and on the graded clip at matching times.
              </p>
            )}
            <div className="grid2">
              <label className="field">
                <span>Input profile (source)</span>
                <select
                  value={inputProfile}
                  disabled={running || premiereStills}
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
                <span>Reference profile (graded)</span>
                <select
                  value={referenceProfile}
                  disabled={running || premiereStills}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setReferenceProfile(e.target.value)}
                >
                  <option value="auto">Auto ({defaultReferenceProfile(inputProfile)})</option>
                  <option value="rec709">rec709</option>
                  <option value="rec2020">rec2020</option>
                  <option value="apple_log">apple_log</option>
                  <option value="slog3">slog3</option>
                  <option value="slog3_sgamut3cine">slog3_sgamut3cine</option>
                </select>
              </label>
            </div>
            {inputProfile === "apple_log" && (
              <label className="field">
                <span>Apply the cube in</span>
                <select
                  value={premiereExport ? "premiere" : "log"}
                  disabled={running}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setPremiereExport(e.target.value === "premiere")}
                >
                  <option value="premiere">Premiere (clip color space Apple Log, Lumetri Input LUT)</option>
                  <option value="log">FFmpeg or Resolve (raw Apple Log codes)</option>
                </select>
              </label>
            )}
            {isLogProfile(inputProfile) && (
              <p className="hint">
                {inputProfile === "apple_log" && premiereExport
                  ? "The cube expects what Premiere feeds Lumetri after its Apple Log color management, so leave the clip on Apple Log and load the cube as the Lumetri Input LUT."
                  : "The cube applies directly to raw log footage in FFmpeg or Resolve."}{" "}
                Graded references stay display-referred, so keep the reference profile on rec709.
              </p>
            )}
            {isLogProfile(resolvedReference) && (
              <p className="hint">
                Reference profile is a log profile: the graded reference will be decoded as log and the cube
                exports in legacy working-domain mode, which does not match in Premiere. Use Auto (rec709)
                unless you need the legacy path.
              </p>
            )}
            <label className="check">
              <input
                type="checkbox"
                checked={alignedPairs}
                disabled={running || premiereStills}
                onChange={(e: ChangeEvent<HTMLInputElement>) => applyPairedPreset(e.target.checked)}
              />
              Same-frame pairs: source and reference are the same frames before and after grading (for
              example Capture both at matched time). Fits the grade per pixel with a longer run (1500 plus
              200 iterations).
            </label>
            <div className="grid2">
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
              <div className="grid2">
                <label className="field">
                  <span>Smoothness weight</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={weightTv}
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setWeightTv(Number(e.target.value))
                    }
                  />
                </label>
                <label className="field">
                  <span>Shadow weight</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={weightShadow}
                    disabled={running}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setWeightShadow(Number(e.target.value))
                    }
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
              reference, {inputProfile} to {resolvedReference}, contract v{contractVersion}, {device}, LUT{" "}
              {lutSize}.
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
