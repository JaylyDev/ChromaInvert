export interface JobConfig {
  sourceFrames: string;
  referenceFrames: string;
  outputCube: string;
  strength: number;
  lutSize: number;
  device: string;
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
}

export interface DoneResult {
  exitCode: number;
  summary: string;
}
