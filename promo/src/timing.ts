export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const TOTAL_FRAMES = 1800;

export type SceneKey =
  | 'hook'
  | 'problem'
  | 'promise'
  | 'plan'
  | 'evidence'
  | 'approval'
  | 'trace'
  | 'finale';

export type SceneTiming = {
  key: SceneKey;
  from: number;
  duration: number;
};

export const SCENES: SceneTiming[] = [
  {key: 'hook', from: 0, duration: 180},
  {key: 'problem', from: 180, duration: 210},
  {key: 'promise', from: 390, duration: 210},
  {key: 'plan', from: 600, duration: 330},
  {key: 'evidence', from: 930, duration: 300},
  {key: 'approval', from: 1230, duration: 240},
  {key: 'trace', from: 1470, duration: 180},
  {key: 'finale', from: 1650, duration: 150},
];

export const scene = (key: SceneKey): SceneTiming => {
  const match = SCENES.find((item) => item.key === key);
  if (!match) {
    throw new Error(`Unknown scene: ${key}`);
  }
  return match;
};
