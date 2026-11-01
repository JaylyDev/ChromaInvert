export interface JobConfig {
  sourceFrames: string[];
  referenceFrames: string[];
  outputCube: string;
  inputProfile: string;
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
