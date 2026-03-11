import { Application, Assets, Sprite } from 'pixi.js';

// ---- Screen ----------------------------------------------------------------
const SCREEN_W = 960;
const SCREEN_H = 540;

// ---- Projection (docs/specs/tech/Technical_Challenges_True3D_Doc1.md #12) --
const FOV_H = 60;
const FOCAL = (SCREEN_W / 2) / Math.tan((FOV_H * Math.PI) / 180 / 2);
const SPRITE_REF_DIST = 300;

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

await Assets.load(['/images/enemy01.png', '/images/props01.png']);

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
  '/images/enemy01.png',
  (i) => ({ x: rand50(), y: rand50(), z: 1000 + i * Z_STEP }),
  5,
  SPEED * 0.8,
);

const rand300 = () => (Math.random() - 0.5) * 600; // -300 ~ +300

const props = makeEntities(
  '/images/props01.png',
  (i) => ({ x: rand300(), y: -50, z: 1000 + i * (Z_STEP / 10) }),
  50,
);

const entities: EntityData[] = [...enemies, ...props];

// ---- Game loop -------------------------------------------------------------
app.ticker.add((ticker) => {
  const dt = ticker.deltaMS / 1000;

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
