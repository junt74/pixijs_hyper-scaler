import { Application, Assets, Container, Sprite, TilingSprite } from 'pixi.js';

// ---- Screen ----------------------------------------------------------------
const SCREEN_W = 960;
const SCREEN_H = 540;

// ---- Projection (docs/specs/tech/Technical_Challenges_True3D_Doc1.md #12) --
const FOV_H = 60;
const FOCAL = (SCREEN_W / 2) / Math.tan((FOV_H * Math.PI) / 180 / 2);
const SPRITE_REF_DIST = 300;
const HORIZON_Y = SCREEN_H * 0.46;

// ---- Ground (Space Harrier style pseudo raycaster) -------------------------
const GROUND_SLICE_H = 3;
const CAMERA_HEIGHT = 140;
const GROUND_SCROLL_SPEED = 550;

// ---- Entity definitions ----------------------------------------------------
const Z_NEAR  = 30;
const Z_SPAWN = 3000;
const SPEED   = 600;
const Z_STEP  = 600; // interval between entities of the same type

type EntityData = { x: number; y: number; z: number; speed: number; sprite: Sprite };

const rand50 = () => (Math.random() - 0.5) * 100; // -50 ~ +50

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
  '/assets/images/ground.png',
]);

const groundLayer = new Container();
groundLayer.zIndex = -1_000_000;
app.stage.addChild(groundLayer);

type GroundSlice = {
  stripe: TilingSprite;
  screenY: number;
  dist: number;
  uvScale: number;
  xTileScale: number;
};

const groundSlices: GroundSlice[] = [];
const groundTexture = Assets.get('/assets/images/ground.png');
const GROUND_REPEAT_X_AT_ZERO_DIST = 8;

for (let y = HORIZON_Y; y < SCREEN_H; y += GROUND_SLICE_H) {
  const stripe = new TilingSprite({
    texture: groundTexture,
    width: SCREEN_W,
    height: Math.min(GROUND_SLICE_H + 1, SCREEN_H - y),
  });
  stripe.x = 0;
  stripe.y = y;
  stripe.alpha = 0.98;
  groundLayer.addChild(stripe);

  // y_screen = horizon + focal * cameraHeight / z を z へ逆算
  const dy = Math.max(1, y - HORIZON_Y);
  const dist = (FOCAL * CAMERA_HEIGHT) / dy;
  const uvScale = Math.max(0.0000078125, Math.min(0.000732421875, 4096 / dist));
  const xRepeatCount = Math.max(1, Math.min(GROUND_REPEAT_X_AT_ZERO_DIST, GROUND_REPEAT_X_AT_ZERO_DIST * (dist / (dist + 1200))));
  const xTileScale = Math.max(0.01, SCREEN_W / (Math.max(1, groundTexture.width) * xRepeatCount));

  groundSlices.push({ stripe, screenY: y, dist, uvScale, xTileScale });
}

function makeEntities(
  texture: string,
  makePos: (i: number) => { x: number; y: number; z: number },
  count: number,
  speed: number = SPEED,
): EntityData[] {
  return Array.from({ length: count }, (_, i) => {
    const { x, y, z } = makePos(i);
    const sprite = Sprite.from(texture);
    sprite.anchor.set(0.5);
    app.stage.addChild(sprite);
    return { x, y, z, speed, sprite };
  });
}

const enemies = makeEntities(
  '/assets/images/enemy01.png',
  (i) => ({ x: rand50(), y: rand50(), z: 1000 + i * Z_STEP }),
  5,
  SPEED * 0.8,
);

const rand300 = () => (Math.random() - 0.5) * 600; // -300 ~ +300

const props = makeEntities(
  '/assets/images/props01.png',
  (i) => ({ x: rand300(), y: -50, z: 1000 + i * (Z_STEP / 10) }),
  50,
);

const entities: EntityData[] = [...enemies, ...props];

// ---- Game loop -------------------------------------------------------------
app.ticker.add((ticker) => {
  const dt = ticker.deltaMS / 1000;
  const move = GROUND_SCROLL_SPEED * dt;

  for (const s of groundSlices) {
    // 遠いラインはゆっくり、近いラインは速く流れるようにして擬似3D感を出す
    const speedFactor = Math.max(0.2, Math.min(4, 1200 / s.dist));
    s.stripe.tileScale.set(s.xTileScale, s.uvScale);
    s.stripe.tilePosition.x += move * speedFactor * s.xTileScale;
    s.stripe.tilePosition.y = s.dist * 0.08 * s.uvScale;
    s.stripe.alpha = 0.25 + ((s.screenY - HORIZON_Y) / (SCREEN_H - HORIZON_Y)) * 0.75;
  }

  for (const e of entities) {
    e.z -= e.speed * dt;
    if (e.z <= Z_NEAR) {
      e.z = Z_SPAWN;
    }

    const scale = SPRITE_REF_DIST / e.z;
    e.sprite.x      = (e.x / e.z) * FOCAL + SCREEN_W / 2;
    e.sprite.y      = (-e.y / e.z) * FOCAL + SCREEN_H / 2;
    e.sprite.scale.set(scale);
    e.sprite.zIndex = -e.z; // closer = higher zIndex (docs #13)
  }
});
