import type { DoneResult, EnvStatus, FrameGrab, JobConfig, ProgressUpdate, SetupProgress, VideoProbe, VideoTools } from "../electron/types";

export interface GuiBridge {
  runJob: (config: JobConfig) => Promise<DoneResult>;
  cancelJob: () => Promise<void>;
  pickSourceFrames: () => Promise<string[]>;
  pickReferenceFrames: () => Promise<string[]>;
  pickSourceVideo: () => Promise<string | null>;
  pickReferenceVideo: () => Promise<string | null>;
  videoTools: () => Promise<VideoTools>;
  probeVideo: (videoPath: string) => Promise<VideoProbe>;
  grabFrame: (videoPath: string, timestamp: number, kind: string, outputDir: string) => Promise<FrameGrab>;
  saveCapture: (pngBase64: string, timestamp: number, kind: string, outputDir: string) => Promise<FrameGrab>;
  pickOutputCube: (suggestedPath: string) => Promise<string | null>;
  pickWeights: () => Promise<string | null>;
  checkEnv: () => Promise<EnvStatus>;
  setupEnv: () => Promise<DoneResult>;
  cancelSetup: () => Promise<void>;
  onProgress: (cb: (update: ProgressUpdate) => void) => void;
  onLog: (cb: (line: string) => void) => void;
  onSetupProgress: (cb: (update: SetupProgress) => void) => void;
  onSetupLog: (cb: (line: string) => void) => void;
}

declare global {
  interface Window {
    chromainvert?: GuiBridge;
  }
}

export function getBridge(): GuiBridge | null {
  return window.chromainvert ?? null;
}

export function isDesktop(): boolean {
  return window.chromainvert !== undefined;
}
