export interface JobConfig {
  sourceFrames: string[];
  referenceFrames: string[];
  referenceOnly: boolean;
  customWeights: string;
  outputCube: string;
  inputProfile: string;
  referenceProfile: string;
  weightTv: number;
  weightShadow: number;
  weightPaired: number;
  premiereExport: boolean;
  strength: number;
  lutSize: number;
  coarseSize: number;
  iterations: number;
  fineIterations: number;
  seed: number;
  device: string;
  deterministic: boolean;
}

export enum RunPhase {
  Idle,
  Running,
  Done,
  Failed
}

export interface ProgressUpdate {
  percent: number;
  loss: number;
  iter: number;
  iters: number;
}

export interface DoneResult {
  exitCode: number;
  summary: string;
}

export interface VideoProbe {
  path: string;
  duration: number;
  width: number;
  height: number;
  fps: string;
  codec: string;
  error: string;
}

export interface FrameGrab {
  framePath: string;
  timestamp: number;
  error: string;
}
