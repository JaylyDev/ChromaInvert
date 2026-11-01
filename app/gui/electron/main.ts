import { app, BrowserWindow, ipcMain } from "electron";
import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import type { DoneResult, JobConfig, ProgressUpdate } from "../src/types";

interface ProgressLine {
  event: string;
  iter: number;
  iters: number;
  loss: number;
}

function splitList(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function isProgressLine(value: unknown): value is ProgressLine {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const rec = value as Record<string, unknown>;
  return rec.event === "progress" && typeof rec.loss === "number";
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
          const update: ProgressUpdate = {
            percent: Math.round((value.iter / Math.max(1, value.iters)) * 100),
            loss: value.loss
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
    width: 1100,
    height: 750,
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

ipcMain.handle("job:run", (event, payload: JobConfig): Promise<DoneResult> => {
  const sender = event.sender;
  const outDir = dirname(payload.outputCube);
  const workdir = outDir === "" ? "work" : outDir;
  const jobPath = join(workdir, "job.json");
  const reportPath = join(workdir, "report.json");
  const job = {
    contract_version: 1,
    source_frames: splitList(payload.sourceFrames),
    reference_frames: splitList(payload.referenceFrames),
    input_profile: "rec709",
    lut_size: payload.lutSize,
    strength: payload.strength,
    device: payload.device,
    output_cube: payload.outputCube,
    report_json: reportPath
  };
  currentChild?.kill();
  return writeFile(jobPath, JSON.stringify(job, null, 2), "utf8").then(
    (): Promise<DoneResult> =>
      new Promise<DoneResult>((resolve) => {
        const child: ChildProcess = spawn("python", ["-m", "chromainvert", "run", jobPath], { cwd: process.cwd() });
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
          resolve({ exitCode, summary: exitCode === 0 ? "Done: " + payload.outputCube : "Failed: " + tail.slice(-500) });
        });
      })
  );
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
