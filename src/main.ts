import { Application, Assets } from 'pixi.js';

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
  '/assets/images/props01.png',
]);

const stage = await loadStage(app, '/assets/stages/world.json', {
  focalX: FOCAL_X,
  focalY: FOCAL_Y,
  screenW: SCREEN_W,
  screenH: SCREEN_H,
  spritePixelsPerUnit: 32,
  zNear: Z_NEAR,
});

// ---- Game loop -------------------------------------------------------------
app.ticker.add((ticker) => {
  const dt = ticker.deltaMS / 1000;
  stage.update(dt);
});
