import { contextBridge, ipcRenderer } from "electron";
import type { IpcRendererEvent } from "electron";
import type { DoneResult, JobConfig, ProgressUpdate } from "../src/types";

contextBridge.exposeInMainWorld("chromainvert", {
  runJob: (config: JobConfig): Promise<DoneResult> => ipcRenderer.invoke("job:run", config),
  cancelJob: (): Promise<void> => ipcRenderer.invoke("job:cancel"),
  pickSourceFrames: (): Promise<string[]> => ipcRenderer.invoke("job:pickSources"),
  pickReferenceFrames: (): Promise<string[]> => ipcRenderer.invoke("job:pickReferences"),
  pickOutputCube: (suggestedPath: string): Promise<string | null> =>
    ipcRenderer.invoke("job:pickOutput", suggestedPath),
  onProgress: (cb: (update: ProgressUpdate) => void): void => {
    ipcRenderer.on("job:progress", (_event: IpcRendererEvent, update: ProgressUpdate) => cb(update));
  },
  onLog: (cb: (line: string) => void): void => {
    ipcRenderer.on("job:log", (_event: IpcRendererEvent, line: string) => cb(line));
  }
});
