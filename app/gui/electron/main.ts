import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { spawn, spawnSync } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { mkdir, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve as resolvePath } from "node:path";
import type { FileFilter, IpcMainInvokeEvent } from "electron";
import type { DoneResult, FrameGrab, JobConfig, ProgressUpdate, VideoProbe } from "../src/types";

interface ProgressLine {
  event: string;
  iter: number;
  iters: number;
  loss: number;
}

interface JobFile {
  contract_version: number;
  source_frames: string[];
  reference_frames: string[];
  reference_only: boolean;
  predict_weights: string;
  input_profile: string;
  reference_profile: string;
  weight_tv: number;
  weight_shadow: number;
  weight_paired: number;
  coarse_size: number;
  lut_size: number;
  iterations: number;
  fine_iterations: number;
  strength: number;
  seed: number;
  device: string;
  deterministic: boolean;
  output_cube: string;
  report_json: string;
}

const IMAGE_FILTERS: FileFilter[] = [
  { name: "Images", extensions: ["png", "tif", "tiff", "bmp", "jpg", "jpeg"] },
  { name: "All files", extensions: ["*"] }
];

const CUBE_FILTERS: FileFilter[] = [
  { name: "LUT cube", extensions: ["cube"] },
  { name: "All files", extensions: ["*"] }
];

const VIDEO_FILTERS: FileFilter[] = [
  { name: "Videos", extensions: ["mp4", "mov", "m4v", "mkv", "avi", "webm"] },
  { name: "All files", extensions: ["*"] }
];

interface FfprobeStream {
  codecName: string;
  width: number;
  height: number;
  fps: string;
}

function emptyProbe(videoPath: string, error: string): VideoProbe {
  return { path: videoPath, duration: -1, width: 0, height: 0, fps: "unknown", codec: "unknown", error };
}

function toFps(raw: unknown): string {
  if (typeof raw !== "string" || raw === "" || raw === "0/0") {
    return "unknown";
  }
  const parts = raw.split("/");
  if (parts.length !== 2) {
    return raw;
  }
  const num = Number(parts[0]);
  const den = Number(parts[1]);
  if (!Number.isFinite(num) || !Number.isFinite(den) || den === 0) {
    return "unknown";
  }
  return String(Math.round((num / den) * 1000) / 1000);
}

function toStream(value: unknown): FfprobeStream {
  const rec = typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
  const width = typeof rec.width === "number" ? rec.width : Number(rec.width);
  const height = typeof rec.height === "number" ? rec.height : Number(rec.height);
  const codec = typeof rec.codec_name === "string" ? rec.codec_name : "unknown";
  return {
    codecName: codec,
    width: Number.isFinite(width) ? Math.round(width) : 0,
    height: Number.isFinite(height) ? Math.round(height) : 0,
    fps: toFps(rec.avg_frame_rate)
  };
}

function buildProbe(target: string, value: unknown): VideoProbe {
  const rec = typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
  const streams = Array.isArray(rec.streams) ? rec.streams : [];
  const stream = toStream(streams.length > 0 ? streams[0] : null);
  const format = typeof rec.format === "object" && rec.format !== null ? (rec.format as Record<string, unknown>) : {};
  const duration = Number(format.duration);
  return {
    path: target,
    duration: Number.isFinite(duration) && duration > 0 ? duration : -1,
    width: stream.width,
    height: stream.height,
    fps: stream.fps,
    codec: stream.codecName,
    error: ""
  };
}

function probeVideoPath(videoPath: string): Promise<VideoProbe> {
  const target = videoPath.trim();
  if (target === "") {
    return Promise.resolve(emptyProbe(videoPath, "Pick a video file first."));
  }
  const probed = spawnSync("ffprobe", [
    "-v", "error",
    "-select_streams", "v:0",
    "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
    "-show_entries", "format=duration",
    "-of", "json",
    target
  ], { encoding: "utf8" });
  if (probed.status !== 0) {
    const detail = String(probed.stderr ?? probed.error ?? "ffprobe failed").trim().slice(-300);
    return Promise.resolve(emptyProbe(target, detail === "" ? "ffprobe failed." : detail));
  }
  return Promise.resolve(String(probed.stdout)).then(
    (text: string): unknown => JSON.parse(text)
  ).then(
    (value: unknown): VideoProbe => buildProbe(target, value),
    (): VideoProbe => emptyProbe(target, "ffprobe returned unreadable JSON.")
  );
}

function grabFrameAt(videoPath: string, timestamp: number, kind: string, outputDir: string): Promise<FrameGrab> {
  const target = videoPath.trim();
  const safeKind = kind === "source" || kind === "reference" ? kind : "frame";
  const time = Number.isFinite(timestamp) && timestamp >= 0 ? timestamp : 0;
  if (target === "") {
    return Promise.resolve({ framePath: "", timestamp: time, error: "Pick a video file first." });
  }
  const baseDir = outputDir.trim() === "" ? "work" : outputDir.trim();
  const workdirAbs = resolvePath(process.cwd(), baseDir);
  const stampText = time.toFixed(2).replace(".", "p");
  const fileName = safeKind + "_" + stampText + "s_" + String(Date.now() % 100000) + ".png";
  const absOut = join(workdirAbs, "video_frames", fileName);
  return mkdir(dirname(absOut), { recursive: true }).then(
    (): Promise<FrameGrab> =>
      new Promise<FrameGrab>((resolve) => {
        const child: ChildProcess = spawn("ffmpeg", [
          "-y", "-ss", String(time), "-i", target,
          "-frames:v", "1", "-pix_fmt", "rgb24", absOut
        ], { cwd: process.cwd() });
        let detail = "";
        child.stderr?.on("data", (chunk: Buffer) => {
          detail = (detail + chunk.toString("utf8")).slice(-500);
        });
        child.on("error", () => {
          resolve({ framePath: "", timestamp: time, error: "ffmpeg was not found on PATH." });
        });
        child.on("close", (code: number | null) => {
          if (code !== 0) {
            resolve({ framePath: "", timestamp: time, error: detail === "" ? "ffmpeg frame grab failed." : detail });
            return;
          }
          stat(absOut).then(
            () => resolve({ framePath: absOut, timestamp: time, error: "" }),
            () => resolve({ framePath: "", timestamp: time, error: "ffmpeg produced no output file." })
          );
        });
      })
  );
}

function isProgressLine(value: unknown): value is ProgressLine {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const rec = value as Record<string, unknown>;
  return rec.event === "progress" && typeof rec.loss === "number";
}

function toProfile(raw: string): string {
  const profile = raw.trim() === "" ? "rec709" : raw.trim();
  return profile;
}

function defaultReferenceProfile(profile: string): string {
  if (profile === "apple_log" || profile.indexOf("slog3") === 0) {
    return "rec709";
  }
  return profile;
}

function toReferenceProfile(inputProfile: string, raw: string): string {
  const trimmed = raw.trim();
  if (trimmed === "" || trimmed === "auto") {
    return defaultReferenceProfile(inputProfile);
  }
  return trimmed;
}

function toWeight(raw: unknown, fallback: number): number {
  return typeof raw === "number" && Number.isFinite(raw) && raw >= 0 ? raw : fallback;
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

function isLogProfile(profile: string): boolean {
  return profile === "apple_log" || profile.indexOf("slog3") === 0;
}

function contractVersionFor(profile: string): number {
  return profile.indexOf("slog3") === 0 ? 2 : 1;
}

let currentChild: ChildProcess | null = null;

function parseLine(line: string, sender: Electron.WebContents): void {
  if (!line.startsWith("{")) {
    sender.send("job:log", line);
    return;
  }
  Promise.resolve()
    .then((): unknown => JSON.parse(line))
    .then(
      (value: unknown): void => {
        if (isProgressLine(value)) {
          const iters = Math.max(1, value.iters);
          const update: ProgressUpdate = {
            percent: Math.round((value.iter / iters) * 100),
            loss: value.loss,
            iter: value.iter,
            iters: value.iters
          };
          sender.send("job:progress", update);
        } else {
          sender.send("job:log", line);
        }
      },
      (): void => {
        sender.send("job:log", line);
      }
    );
}

function createWindow(): void {
  const here = __dirname;
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    title: "ChromaInvert",
    webPreferences: { preload: join(here, "preload.js") }
  });
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl !== undefined && devUrl !== "") {
    void win.loadURL(devUrl);
  } else {
    void win.loadFile(join(here, "../../dist/index.html"));
  }
}

ipcMain.handle("job:pickSources", (event: IpcMainInvokeEvent): Promise<string[]> => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win === null) {
    return Promise.resolve([]);
  }
  return dialog
    .showOpenDialog(win, {
      title: "Select source frames",
      properties: ["openFile", "multiSelections"],
      filters: IMAGE_FILTERS
    })
    .then((result) => (result.canceled ? [] : result.filePaths));
});

ipcMain.handle("job:pickReferences", (event: IpcMainInvokeEvent): Promise<string[]> => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win === null) {
    return Promise.resolve([]);
  }
  return dialog
    .showOpenDialog(win, {
      title: "Select reference frames",
      properties: ["openFile", "multiSelections"],
      filters: IMAGE_FILTERS
    })
    .then((result) => (result.canceled ? [] : result.filePaths));
});

ipcMain.handle("video:pickSource", (event: IpcMainInvokeEvent): Promise<string | null> => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win === null) {
    return Promise.resolve(null);
  }
  return dialog
    .showOpenDialog(win, {
      title: "Select source video (ungraded)",
      properties: ["openFile"],
      filters: VIDEO_FILTERS
    })
    .then((result) => (result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0]));
});

ipcMain.handle("video:pickReference", (event: IpcMainInvokeEvent): Promise<string | null> => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win === null) {
    return Promise.resolve(null);
  }
  return dialog
    .showOpenDialog(win, {
      title: "Select reference video (graded)",
      properties: ["openFile"],
      filters: VIDEO_FILTERS
    })
    .then((result) => (result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0]));
});

ipcMain.handle(
  "video:probe",
  (event: IpcMainInvokeEvent, videoPath: string): Promise<VideoProbe> => probeVideoPath(videoPath)
);

ipcMain.handle(
  "video:grab",
  (
    event: IpcMainInvokeEvent,
    videoPath: string,
    timestamp: number,
    kind: string,
    outputDir: string
  ): Promise<FrameGrab> => grabFrameAt(videoPath, timestamp, kind, outputDir)
);

ipcMain.handle(
  "job:pickOutput",
  (event: IpcMainInvokeEvent, suggestedPath: string): Promise<string | null> => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (win === null) {
      return Promise.resolve(null);
    }
    return dialog
      .showSaveDialog(win, {
        title: "Save output LUT",
        defaultPath: suggestedPath === "" ? "out.cube" : suggestedPath,
        filters: CUBE_FILTERS
      })
      .then((result) => (result.canceled || result.filePath === undefined ? null : result.filePath));
  }
);

ipcMain.handle("job:pickWeights", (event: IpcMainInvokeEvent): Promise<string | null> => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win === null) {
    return Promise.resolve(null);
  }
  return dialog
    .showOpenDialog(win, {
      title: "Select predictor weights",
      properties: ["openFile"],
      filters: [{ name: "Weights", extensions: ["pt"] }, { name: "All files", extensions: ["*"] }]
    })
    .then((result) => (result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0]));
});

ipcMain.handle("job:run", (event: IpcMainInvokeEvent, payload: JobConfig): Promise<DoneResult> => {
  const sender = event.sender;
  if (payload.outputCube.trim() === "") {
    return Promise.resolve({ exitCode: 1, summary: "Pick an output .cube path." });
  }
  if (payload.referenceFrames.length === 0) {
    return Promise.resolve({ exitCode: 1, summary: "Pick at least one reference frame." });
  }
  if (!payload.referenceOnly && payload.sourceFrames.length === 0) {
    return Promise.resolve({ exitCode: 1, summary: "Pick source frames or enable reference-only mode." });
  }
  const profile = toProfile(payload.inputProfile);
  const referenceProfile = toReferenceProfile(profile, payload.referenceProfile);
  const weightTv = toWeight(payload.weightTv, 0.1);
  const weightShadow = toWeight(payload.weightShadow, 0.25);
  const weightPaired = toWeight(payload.weightPaired, 0.0);
  if (isLogProfile(referenceProfile)) {
    if (canonicalProfile(referenceProfile) !== canonicalProfile(profile)) {
      return Promise.resolve({ exitCode: 1, summary: "Reference profile is a log profile: graded references must use a display profile such as rec709." });
    }
  }
  const customWeights = payload.customWeights.trim();
  const checkWeights = payload.referenceOnly
    ? (customWeights === ""
        ? Promise.resolve({
            error: "Pick a predictor weights .pt file: train one with scripts/train_lut_predictor.py --data-dir data and select it in the weights field.",
            path: "",
          })
        : stat(resolvePath(process.cwd(), customWeights)).then(
            () => ({ error: null as string | null, path: resolvePath(process.cwd(), customWeights) }),
            () => ({ error: `Weights file not found: ${customWeights}`, path: "" })
          ))
    : Promise.resolve({ error: null as string | null, path: "" });
  const outDir = dirname(payload.outputCube);
  const workdir = outDir === "" || outDir === "." ? "work" : outDir;
  const workdirAbs = resolvePath(process.cwd(), workdir);
  const jobPath = join(workdirAbs, "job.json");
  const reportPath = join(workdirAbs, "report.json");
  currentChild?.kill();
  return checkWeights.then((checked: { error: string | null; path: string }): Promise<DoneResult> => {
    if (checked.error !== null) {
      return Promise.resolve({ exitCode: 1, summary: checked.error });
    }
    const job: JobFile = {
      contract_version: contractVersionFor(profile),
      source_frames: payload.referenceOnly ? [] : payload.sourceFrames.map((p) => resolvePath(process.cwd(), p)),
      reference_frames: payload.referenceFrames.map((p) => resolvePath(process.cwd(), p)),
      reference_only: payload.referenceOnly,
      predict_weights: checked.path,
      input_profile: profile,
      reference_profile: referenceProfile,
      weight_tv: weightTv,
      weight_shadow: weightShadow,
      weight_paired: weightPaired,
      coarse_size: payload.coarseSize,
      lut_size: payload.lutSize,
      iterations: payload.iterations,
      fine_iterations: payload.fineIterations,
      strength: payload.strength,
      seed: payload.seed,
      device: payload.device,
      deterministic: payload.deterministic,
      output_cube: resolvePath(process.cwd(), payload.outputCube),
      report_json: reportPath
    };
    return mkdir(workdirAbs, { recursive: true })
    .then(() => writeFile(jobPath, JSON.stringify(job, null, 2), "utf8"))
    .then(
      (): Promise<DoneResult> =>
        new Promise<DoneResult>((resolve) => {
          const child: ChildProcess = spawn("python", ["-m", "chromainvert", "run", jobPath], {
            cwd: process.cwd()
          });
          currentChild = child;
          let tail = "";
          child.stdout?.on("data", (chunk: Buffer) => {
            const text: string = chunk.toString("utf8");
            tail = (tail + text).slice(-8000);
            for (const line of text.split("\n")) {
              const trimmed = line.trim();
              if (trimmed !== "") {
                parseLine(trimmed, sender);
              }
            }
          });
          child.stderr?.on("data", (chunk: Buffer) => {
            sender.send("job:log", chunk.toString("utf8").trim());
          });
          child.on("close", (code: number | null) => {
            currentChild = null;
            const exitCode = code ?? 1;
            resolve({
              exitCode,
              summary: exitCode === 0 ? "Done: " + payload.outputCube : "Failed: " + tail.slice(-500)
            });
          });
        })
    );
  });
});

ipcMain.handle("job:cancel", (): Promise<void> => {
  currentChild?.kill();
  currentChild = null;
  return Promise.resolve();
});

void app.whenReady().then(() => {
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
