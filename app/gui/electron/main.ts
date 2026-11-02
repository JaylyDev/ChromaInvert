import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { mkdir, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve as resolvePath } from "node:path";
import type { FileFilter, IpcMainInvokeEvent } from "electron";
import type { DoneResult, JobConfig, ProgressUpdate } from "../src/types";

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
  const weightsPath = resolvePath(process.cwd(), "engine/chromainvert/predictor_rec709.pt");
  const checkWeights =
    payload.referenceOnly
      ? stat(weightsPath).then(
          () => null,
          () => "Predictor weights missing: train them with scripts/train_lut_predictor.py."
        )
      : Promise.resolve(null);
  const outDir = dirname(payload.outputCube);
  const workdir = outDir === "" || outDir === "." ? "work" : outDir;
  const workdirAbs = resolvePath(process.cwd(), workdir);
  const jobPath = join(workdirAbs, "job.json");
  const reportPath = join(workdirAbs, "report.json");
  const job: JobFile = {
    contract_version: contractVersionFor(profile),
    source_frames: payload.referenceOnly ? [] : payload.sourceFrames.map((p) => resolvePath(process.cwd(), p)),
    reference_frames: payload.referenceFrames.map((p) => resolvePath(process.cwd(), p)),
    reference_only: payload.referenceOnly,
    predict_weights: weightsPath,
    input_profile: profile,
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
  currentChild?.kill();
  return checkWeights.then((weightsError: string | null): Promise<DoneResult> => {
    if (weightsError !== null) {
      return Promise.resolve({ exitCode: 1, summary: weightsError });
    }
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
