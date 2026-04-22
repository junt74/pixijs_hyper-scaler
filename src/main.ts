import { Application, Assets, Graphics, Text } from 'pixi.js';

import { loadStage } from './stage';

// ---- Screen ----------------------------------------------------------------
const SCREEN_W = 960;
const SCREEN_H = 540;

// ---- Projection (docs/specs/tech/Technical_Challenges_True3D_Doc1.md #12) --
const FOV_H = 85;
/** 縦方向も個別に指定（単一 FOCAL だと縦が画面比の関係で狭くなる） */
const FOV_V = 85;
const FOCAL_X = (SCREEN_W / 2) / Math.tan((FOV_H * Math.PI) / 180 / 2);
const FOCAL_Y = (SCREEN_H / 2) / Math.tan((FOV_V * Math.PI) / 180 / 2);
// ---- Stage / camera --------------------------------------------------------
const Z_NEAR = 1;

// ---- App -------------------------------------------------------------------
const app = new Application();

await app.init({
  width: SCREEN_W,
  height: SCREEN_H,
  backgroundColor: 0x000000,
  antialias: false,
});

document.body.appendChild(app.canvas);
app.stage.sortableChildren = true;

function fitCanvas(): void {
  const scale = Math.min(window.innerWidth / SCREEN_W, window.innerHeight / SCREEN_H);
  app.canvas.style.width  = `${SCREEN_W * scale}px`;
  app.canvas.style.height = `${SCREEN_H * scale}px`;
}
window.addEventListener('resize', fitCanvas);
fitCanvas();

await Assets.load([
  '/assets/images/enemy01.png',
  '/assets/images/grass.png',
  '/assets/images/wood.png',
]);

const stage = await loadStage(app, '/assets/stages/world.json', {
  focalX: FOCAL_X,
  focalY: FOCAL_Y,
  screenW: SCREEN_W,
  screenH: SCREEN_H,
  spritePixelsPerUnit: 32,
  zNear: Z_NEAR,
});

const fpsText = new Text({
  text: 'FPS: --',
  style: {
    fill: 0xffffff,
    fontFamily: 'monospace',
    fontSize: 18,
    stroke: { color: 0x000000, width: 3 },
  },
});
fpsText.x = 12;
fpsText.y = 10;
fpsText.zIndex = 1_000_000;
app.stage.addChild(fpsText);

const frameTimeGraph = new Graphics();
frameTimeGraph.x = 12;
frameTimeGraph.y = 40;
frameTimeGraph.zIndex = 1_000_000;
app.stage.addChild(frameTimeGraph);

const frameTimeLabel = new Text({
  text: 'Frame ms (last 1s)',
  style: {
    fill: 0xffffff,
    fontFamily: 'monospace',
    fontSize: 12,
    stroke: { color: 0x000000, width: 2 },
  },
});
frameTimeLabel.x = 12;
frameTimeLabel.y = 138;
frameTimeLabel.zIndex = 1_000_000;
app.stage.addChild(frameTimeLabel);

const profilerText = new Text({
  text: 'update total: -- ms\ncamera: -- ms\nsprites: -- ms\nvisible sprites: --\ncolliders: -- ms\ntriggers: -- ms',
  style: {
    fill: 0xffffff,
    fontFamily: 'monospace',
    fontSize: 12,
    lineHeight: 16,
    stroke: { color: 0x000000, width: 2 },
  },
});
profilerText.x = 12;
profilerText.y = 158;
profilerText.zIndex = 1_000_000;
app.stage.addChild(profilerText);

type FrameSample = {
  deltaMs: number;
  ageMs: number;
};

const frameSamples: FrameSample[] = [];
const FRAME_GRAPH_W = 220;
const FRAME_GRAPH_H = 90;
const FRAME_GRAPH_WINDOW_MS = 1000;
const FRAME_GRAPH_MAX_MS = 50;

function updateFrameTimeGraph(deltaMs: number): void {
  for (const sample of frameSamples) {
    sample.ageMs += deltaMs;
  }

  frameSamples.push({ deltaMs, ageMs: 0 });

  while (frameSamples.length > 0 && frameSamples[0].ageMs > FRAME_GRAPH_WINDOW_MS) {
    frameSamples.shift();
  }

  frameTimeGraph.clear();
  frameTimeGraph.rect(0, 0, FRAME_GRAPH_W, FRAME_GRAPH_H);
  frameTimeGraph.fill({ color: 0x081018, alpha: 0.7 });
  frameTimeGraph.stroke({ color: 0xffffff, alpha: 0.35, width: 1 });

  for (const markerMs of [16.67, 33.33]) {
    const y = FRAME_GRAPH_H - Math.min(1, markerMs / FRAME_GRAPH_MAX_MS) * FRAME_GRAPH_H;
    frameTimeGraph.moveTo(0, y);
    frameTimeGraph.lineTo(FRAME_GRAPH_W, y);
    frameTimeGraph.stroke({ color: 0xffffff, alpha: 0.15, width: 1 });
  }

  if (frameSamples.length === 0) {
    return;
  }

  const points: number[] = [];
  for (const sample of frameSamples) {
    const x = FRAME_GRAPH_W - (sample.ageMs / FRAME_GRAPH_WINDOW_MS) * FRAME_GRAPH_W;
    const normalizedDelta = Math.min(sample.deltaMs, FRAME_GRAPH_MAX_MS) / FRAME_GRAPH_MAX_MS;
    const y = FRAME_GRAPH_H - normalizedDelta * FRAME_GRAPH_H;
    points.push(x, y);
  }

  if (points.length >= 4) {
    frameTimeGraph.poly(points);
    frameTimeGraph.stroke({ color: 0x66ffcc, width: 2 });
  }
}

// ---- Game loop -------------------------------------------------------------
app.ticker.add((ticker) => {
  const dt = ticker.deltaMS / 1000;
  const profile = stage.update(dt);
  fpsText.text = `FPS: ${ticker.FPS.toFixed(1)}`;
  profilerText.text = [
    `update total: ${profile.totalMs.toFixed(2)} ms`,
    `camera: ${profile.cameraMs.toFixed(2)} ms`,
    `sprites: ${profile.spritesMs.toFixed(2)} ms`,
    `visible sprites: ${profile.visibleSpriteCount}`,
    `colliders: ${profile.collidersMs.toFixed(2)} ms`,
    `triggers: ${profile.triggersMs.toFixed(2)} ms`,
  ].join('\n');
  updateFrameTimeGraph(ticker.deltaMS);
});
