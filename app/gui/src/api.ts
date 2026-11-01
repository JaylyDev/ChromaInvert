import type { DoneResult, JobConfig, ProgressUpdate } from "./types";

export interface GuiBridge {
  runJob: (config: JobConfig) => Promise<DoneResult>;
  cancelJob: () => Promise<void>;
  onProgress: (cb: (update: ProgressUpdate) => void) => void;
  onLog: (cb: (line: string) => void) => void;
}

declare global {
  interface Window {
    chromainvert?: GuiBridge;
  }
}

export function getBridge(): GuiBridge | null {
  return window.chromainvert ?? null;
}
