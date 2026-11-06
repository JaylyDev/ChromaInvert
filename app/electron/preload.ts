import { contextBridge, ipcRenderer } from "electron";
import type { IpcRendererEvent } from "electron";
import type { DoneResult, EnvStatus, FrameGrab, JobConfig, ProgressUpdate, SetupProgress, VideoProbe } from "./types";

contextBridge.exposeInMainWorld("chromainvert", {
  runJob: (config: JobConfig): Promise<DoneResult> => ipcRenderer.invoke("job:run", config),
  cancelJob: (): Promise<void> => ipcRenderer.invoke("job:cancel"),
  pickSourceFrames: (): Promise<string[]> => ipcRenderer.invoke("job:pickSources"),
  pickReferenceFrames: (): Promise<string[]> => ipcRenderer.invoke("job:pickReferences"),
  pickSourceVideo: (): Promise<string | null> => ipcRenderer.invoke("video:pickSource"),
  pickReferenceVideo: (): Promise<string | null> => ipcRenderer.invoke("video:pickReference"),
  probeVideo: (videoPath: string): Promise<VideoProbe> => ipcRenderer.invoke("video:probe", videoPath),
  grabFrame: (videoPath: string, timestamp: number, kind: string, outputDir: string): Promise<FrameGrab> =>
    ipcRenderer.invoke("video:grab", videoPath, timestamp, kind, outputDir),
  pickOutputCube: (suggestedPath: string): Promise<string | null> =>
    ipcRenderer.invoke("job:pickOutput", suggestedPath),
  pickWeights: (): Promise<string | null> => ipcRenderer.invoke("job:pickWeights"),
  checkEnv: (): Promise<EnvStatus> => ipcRenderer.invoke("env:check"),
  setupEnv: (): Promise<DoneResult> => ipcRenderer.invoke("env:setup"),
  cancelSetup: (): Promise<void> => ipcRenderer.invoke("env:cancel"),
  onSetupProgress: (cb: (update: SetupProgress) => void): void => {
    ipcRenderer.on("setup:progress", (_event: IpcRendererEvent, update: SetupProgress) => cb(update));
  },
  onSetupLog: (cb: (line: string) => void): void => {
    ipcRenderer.on("setup:log", (_event: IpcRendererEvent, line: string) => cb(line));
  },
  onProgress: (cb: (update: ProgressUpdate) => void): void => {
    ipcRenderer.on("job:progress", (_event: IpcRendererEvent, update: ProgressUpdate) => cb(update));
  },
  onLog: (cb: (line: string) => void): void => {
    ipcRenderer.on("job:log", (_event: IpcRendererEvent, line: string) => cb(line));
  }
});
