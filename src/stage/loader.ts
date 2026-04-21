import type { Application } from 'pixi.js';
import { Assets, Filter, Graphics, Sprite, Texture, UniformGroup } from 'pixi.js';

import { parseStageData, type StageCollider, type StageDataV1, type StageTrigger, type StageWaypoint } from './schema';

type ProjectionConfig = {
  focalX: number;
  focalY: number;
  screenW: number;
  screenH: number;
  spritePixelsPerUnit: number;
  zNear: number;
};

type CameraPoint = {
  x: number;
  y: number;
  z: number;
  yaw: number;
};

type StageSpriteInstance = {
  id: string;
  type: string;
  worldX: number;
  worldY: number;
  worldZ: number;
  worldWidth: number;
  worldHeight: number;
  sprite: Sprite;
};

type ProjectedPoint = {
  x: number;
  y: number;
  z: number;
};

const FILTER_VERTEX_SRC = `
in vec2 aPosition;
out vec2 vTextureCoord;

uniform vec4 uInputSize;
uniform vec4 uOutputFrame;
uniform vec4 uOutputTexture;

vec4 filterVertexPosition(void)
{
  vec2 position = aPosition * uOutputFrame.zw + uOutputFrame.xy;
  position.x = position.x * (2.0 / uOutputTexture.x) - 1.0;
  position.y = (position.y * (2.0 * uOutputTexture.z / uOutputTexture.y)) - uOutputTexture.z;

  return vec4(position, 0.0, 1.0);
}

vec2 filterTextureCoord(void)
{
  return aPosition * (uOutputFrame.zw * uInputSize.zw);
}

void main(void)
{
  gl_Position = filterVertexPosition();
  vTextureCoord = filterTextureCoord();
}
`;

const ALPHA_CUTOUT_FRAGMENT_SRC = `
in vec2 vTextureCoord;
out vec4 finalColor;

uniform sampler2D uTexture;
uniform float uAlphaCutoff;

void main(void)
{
  vec4 sampleColor = texture(uTexture, vTextureCoord);

  if (sampleColor.a < uAlphaCutoff) {
    discard;
  }

  vec3 opaqueColor = sampleColor.rgb;

  if (sampleColor.a > 0.0) {
    opaqueColor /= sampleColor.a;
  }

  finalColor = vec4(opaqueColor, 1.0);
}
`;

const ALPHA_CUTOUT_WGSL_SRC = `
struct GlobalFilterUniforms {
  uInputSize: vec4<f32>,
  uInputPixel: vec4<f32>,
  uInputClamp: vec4<f32>,
  uOutputFrame: vec4<f32>,
  uGlobalFrame: vec4<f32>,
  uOutputTexture: vec4<f32>,
};

struct CutoutUniforms {
  uAlphaCutoff: f32,
};

@group(0) @binding(0) var<uniform> gfu: GlobalFilterUniforms;
@group(0) @binding(1) var uTexture: texture_2d<f32>;
@group(0) @binding(2) var uSampler: sampler;
@group(1) @binding(0) var<uniform> cutoutUniforms: CutoutUniforms;

struct VSOutput {
  @builtin(position) position: vec4<f32>,
  @location(0) uv: vec2<f32>,
};

fn filterVertexPosition(aPosition: vec2<f32>) -> vec4<f32>
{
  var position = aPosition * gfu.uOutputFrame.zw + gfu.uOutputFrame.xy;
  position.x = position.x * (2.0 / gfu.uOutputTexture.x) - 1.0;
  position.y = (position.y * (2.0 * gfu.uOutputTexture.z / gfu.uOutputTexture.y)) - gfu.uOutputTexture.z;

  return vec4(position, 0.0, 1.0);
}

fn filterTextureCoord(aPosition: vec2<f32>) -> vec2<f32>
{
  return aPosition * (gfu.uOutputFrame.zw * gfu.uInputSize.zw);
}

@vertex
fn mainVertex(@location(0) aPosition: vec2<f32>) -> VSOutput
{
  return VSOutput(
    filterVertexPosition(aPosition),
    filterTextureCoord(aPosition)
  );
}

@fragment
fn mainFragment(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32>
{
  let sampleColor = textureSample(uTexture, uSampler, uv);

  if (sampleColor.a < cutoutUniforms.uAlphaCutoff) {
    discard;
  }

  return vec4(sampleColor.rgb, 1.0);
}
`;

export type LoadedStage = {
  data: StageDataV1;
  update: (dt: number) => void;
};

type WaypointSegment = {
  from: StageWaypoint;
  to: StageWaypoint;
  length: number;
};

type WaypointPath = {
  segments: WaypointSegment[];
  totalLength: number;
};

function projectPoint(
  worldX: number,
  worldY: number,
  worldZ: number,
  camera: CameraPoint,
  config: ProjectionConfig,
): ProjectedPoint | null {
  const dx = worldX - camera.x;
  const localY = worldY - camera.y;
  const dz = worldZ - camera.z;
  const cosYaw = Math.cos(camera.yaw);
  const sinYaw = Math.sin(camera.yaw);
  const localX = (cosYaw * dx) - (sinYaw * dz);
  const localZ = (sinYaw * dx) + (cosYaw * dz);
  if (localZ <= config.zNear) {
    return null;
  }

  return {
    x: (localX / localZ) * config.focalX + config.screenW / 2,
    y: (-localY / localZ) * config.focalY + config.screenH / 2,
    z: localZ,
  };
}

function makeVolumeGraphics(color: number): Graphics {
  const graphics = new Graphics();
  graphics.zIndex = 850_000;
  graphics.alpha = 0.9;
  graphics.tint = color;
  return graphics;
}

function selectSpriteTexturePath(type: string): string {
  switch (type.toLowerCase()) {
    case 'enemy':
    case 'enemya':
      return '/assets/images/enemy01.png';
    case 'props':
    case 'prop':
    default:
      return '/assets/images/props01.png';
  }
}

function createAlphaCutoutFilter(alphaCutoff: number): Filter {
  return Filter.from({
    gpu: {
      vertex: {
        source: ALPHA_CUTOUT_WGSL_SRC,
        entryPoint: 'mainVertex',
      },
      fragment: {
        source: ALPHA_CUTOUT_WGSL_SRC,
        entryPoint: 'mainFragment',
      },
    },
    gl: {
      vertex: FILTER_VERTEX_SRC,
      fragment: ALPHA_CUTOUT_FRAGMENT_SRC,
      name: 'alpha-cutout-filter',
    },
    resources: {
      cutoutUniforms: new UniformGroup({
        uAlphaCutoff: { value: alphaCutoff, type: 'f32' },
      }),
    },
  });
}

function colorForSpriteType(type: string): number {
  switch (type.toLowerCase()) {
    case 'enemy':
    case 'enemya':
      return 0xff5a5f;
    case 'props':
    case 'prop':
      return 0x5ae08a;
    default:
      return 0x66ccff;
  }
}

function colliderScreenSize(collider: StageCollider, projectedZ: number, config: ProjectionConfig): { width: number; height: number } {
  return {
    width: Math.max(2, (collider.halfExtents.x * 2 / projectedZ) * config.focalX),
    height: Math.max(2, (collider.halfExtents.y * 2 / projectedZ) * config.focalY),
  };
}

function triggerScreenSize(trigger: StageTrigger, projectedZ: number, config: ProjectionConfig): { width: number; height: number } {
  return {
    width: Math.max(2, (trigger.halfExtents.x * 2 / projectedZ) * config.focalX),
    height: Math.max(2, (trigger.halfExtents.y * 2 / projectedZ) * config.focalY),
  };
}

function drawColliderVolumes(
  graphics: Graphics,
  colliders: StageCollider[],
  camera: CameraPoint,
  config: ProjectionConfig,
): void {
  graphics.clear();
  graphics.setStrokeStyle({ width: 1.5, color: 0xffcc33, alpha: 0.95 });

  for (const collider of colliders) {
    const projected = projectPoint(
      collider.position.x,
      collider.position.y,
      collider.position.z,
      camera,
      config,
    );
    if (projected === null) {
      continue;
    }

    const { width, height } = colliderScreenSize(collider, projected.z, config);
    graphics.rect(projected.x - width / 2, projected.y - height / 2, width, height);
    graphics.stroke();
  }
}

function drawTriggerVolumes(
  graphics: Graphics,
  triggers: StageTrigger[],
  camera: CameraPoint,
  config: ProjectionConfig,
): void {
  graphics.clear();
  graphics.setStrokeStyle({ width: 1.5, color: 0xff6699, alpha: 0.95 });

  for (const trigger of triggers) {
    const projected = projectPoint(
      trigger.position.x,
      trigger.position.y,
      trigger.position.z,
      camera,
      config,
    );
    if (projected === null) {
      continue;
    }

    const { width, height } = triggerScreenSize(trigger, projected.z, config);
    graphics.rect(projected.x - width / 2, projected.y - height / 2, width, height);
    graphics.stroke();
  }
}

function makeStageSpriteInstances(
  app: Application,
  data: StageDataV1,
  config: ProjectionConfig,
): StageSpriteInstance[] {
  const alphaCutoutFilter = createAlphaCutoutFilter(0.5);

  return data.sprites.map((stageSprite) => {
    const texturePath = selectSpriteTexturePath(stageSprite.type);
    const hasLoadedTexture = Assets.get(texturePath) !== undefined;
    const sprite = hasLoadedTexture
      ? Sprite.from(texturePath)
      : new Sprite(Texture.WHITE);
    sprite.texture.source.style.scaleMode = 'nearest';
    sprite.anchor.set(0.5, 1.0);
    sprite.tint = colorForSpriteType(stageSprite.type);
    sprite.alpha = 1.0;
    sprite.filters = [alphaCutoutFilter];
    app.stage.addChild(sprite);

    const textureWidth = Math.max(1, sprite.texture.width);
    const textureHeight = Math.max(1, sprite.texture.height);

    return {
      id: stageSprite.id,
      type: stageSprite.type,
      worldX: stageSprite.position.x,
      worldY: stageSprite.position.y,
      worldZ: stageSprite.position.z,
      worldWidth: textureWidth / config.spritePixelsPerUnit,
      worldHeight: textureHeight / config.spritePixelsPerUnit,
      sprite,
    };
  });
}

function updateStageSprites(
  instances: StageSpriteInstance[],
  camera: CameraPoint,
  config: ProjectionConfig,
): void {
  for (const instance of instances) {
    const projected = projectPoint(
      instance.worldX,
      instance.worldY,
      instance.worldZ,
      camera,
      config,
    );

    if (projected === null) {
      instance.sprite.visible = false;
      continue;
    }

    instance.sprite.visible = true;
    instance.sprite.x = projected.x;
    instance.sprite.y = projected.y;
    const spriteScale = config.focalX / projected.z;
    instance.sprite.width = Math.max(1, instance.worldWidth * spriteScale);
    instance.sprite.height = Math.max(1, instance.worldHeight * spriteScale);
    instance.sprite.zIndex = -projected.z;
  }
}

function vec3Distance(a: StageWaypoint['position'], b: StageWaypoint['position']): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const dz = b.z - a.z;

  return Math.hypot(dx, dy, dz);
}

function buildWaypointPath(waypoints: StageWaypoint[]): WaypointPath {
  const segments: WaypointSegment[] = [];
  let totalLength = 0;

  for (let index = 0; index < waypoints.length - 1; index += 1) {
    const from = waypoints[index];
    const to = waypoints[index + 1];
    const length = vec3Distance(from.position, to.position);

    if (length <= 0) {
      continue;
    }

    segments.push({ from, to, length });
    totalLength += length;
  }

  return { segments, totalLength };
}

function sampleWaypointPath(path: WaypointPath, distance: number): { x: number; y: number; z: number } | null {
  if (path.segments.length === 0) {
    return null;
  }

  let remaining = Math.max(0, Math.min(distance, path.totalLength));

  for (const segment of path.segments) {
    if (remaining <= segment.length) {
      const t = segment.length === 0 ? 0 : remaining / segment.length;

      return {
        x: segment.from.position.x + (segment.to.position.x - segment.from.position.x) * t,
        y: segment.from.position.y + (segment.to.position.y - segment.from.position.y) * t,
        z: segment.from.position.z + (segment.to.position.z - segment.from.position.z) * t,
      };
    }

    remaining -= segment.length;
  }

  const last = path.segments[path.segments.length - 1].to.position;
  return { x: last.x, y: last.y, z: last.z };
}

function pingPong(distance: number, length: number): number {
  if (length <= 0) {
    return 0;
  }

  const cycle = length * 2;
  const wrapped = distance % cycle;

  return wrapped <= length ? wrapped : cycle - wrapped;
}

function computeCameraYaw(
  path: WaypointPath,
  travelDistance: number,
  previousYaw: number,
): number {
  if (path.totalLength <= 0) {
    return previousYaw;
  }

  const sampleOffset = Math.min(0.25, path.totalLength * 0.25);
  const forwardDistance = travelDistance % path.totalLength;
  const before = sampleWaypointPath(
    path,
    Math.max(0, forwardDistance - sampleOffset),
  );
  const after = sampleWaypointPath(
    path,
    Math.min(path.totalLength, forwardDistance + sampleOffset),
  );

  if (before === null || after === null) {
    return previousYaw;
  }

  const dirX = after.x - before.x;
  const dirZ = after.z - before.z;
  if (Math.abs(dirX) < 1e-6 && Math.abs(dirZ) < 1e-6) {
    return previousYaw;
  }

  return Math.atan2(dirX, dirZ);
}

export async function loadStage(
  app: Application,
  stagePath: string,
  config: ProjectionConfig,
): Promise<LoadedStage> {
  const rawStage = await Assets.load(stagePath);
  const data = parseStageData(rawStage);

  const colliderGraphics = makeVolumeGraphics(0xffcc33);
  const triggerGraphics = makeVolumeGraphics(0xff6699);

  app.stage.addChild(colliderGraphics);
  app.stage.addChild(triggerGraphics);

  const spriteInstances = makeStageSpriteInstances(app, data, config);
  const waypointPath = buildWaypointPath(data.waypoints);
  let waypointTravelDistance = 0;
  const waypointTravelSpeed = 1;
  let camera: CameraPoint = data.waypoints[0]
    ? { ...data.waypoints[0].position, yaw: 0 }
    : { x: 0, y: 0, z: 0, yaw: 0 };

  return {
    data,
    update(dt: number) {
      waypointTravelDistance += waypointTravelSpeed * dt;
      const movingWaypoint = sampleWaypointPath(
        waypointPath,
        pingPong(waypointTravelDistance, waypointPath.totalLength),
      );
      if (movingWaypoint !== null) {
        camera = {
          ...movingWaypoint,
          yaw: computeCameraYaw(waypointPath, waypointTravelDistance, camera.yaw),
        };
      }

      updateStageSprites(spriteInstances, camera, config);
      drawColliderVolumes(colliderGraphics, data.colliders, camera, config);
      drawTriggerVolumes(triggerGraphics, data.triggers, camera, config);
    },
  };
}
