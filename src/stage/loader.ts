import type { Application } from 'pixi.js';
import { Assets, Graphics, Sprite, Texture } from 'pixi.js';

import {
  parseStageData,
  type StageCollider,
  type StageDataV1,
  type StageSprite,
  type StageTrigger,
  type StageWaypoint,
} from './schema';

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
  rollRadians: number;
  sprite: Sprite;
};

type ProjectedPoint = {
  x: number;
  y: number;
  z: number;
};

type TriggerOverlapState = {
  activeTriggerIds: Set<string>;
  firedTriggerIds: Set<string>;
};

type TriggerRuntimeState = {
  waypointTravelSpeed: number;
  waypointTravelSpeedTransition: {
    active: boolean;
    elapsedMs: number;
    durationMs: number;
    fromSpeed: number;
    toSpeed: number;
  };
};

export type LoadedStage = {
  data: StageDataV1;
  update: (dt: number) => StageUpdateProfile;
};

export type StageUpdateProfile = {
  totalMs: number;
  cameraMs: number;
  spritesMs: number;
  visibleSpriteCount: number;
  collidersMs: number;
  triggersMs: number;
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

function selectSpriteTexturePathByType(type: string): string {
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

function spriteTextureKeyFromName(name?: string): string | null {
  if (typeof name !== 'string') {
    return null;
  }

  const [textureKey] = name.split('.', 1);
  if (textureKey === undefined) {
    return null;
  }

  const normalizedTextureKey = textureKey.trim().toLowerCase();
  return normalizedTextureKey.length > 0 ? normalizedTextureKey : null;
}

function selectSpriteTexturePath(stageSprite: StageSprite): string {
  const textureKey = spriteTextureKeyFromName(stageSprite.name);
  if (textureKey !== null) {
    return `/assets/images/${textureKey}.png`;
  }

  return selectSpriteTexturePathByType(stageSprite.type);
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

function colorForStageSprite(stageSprite: StageSprite): number {
  return spriteTextureKeyFromName(stageSprite.name) !== null
    ? 0xffffff
    : colorForSpriteType(stageSprite.type);
}

function spriteAnchorFromAlignParam(stageSprite: StageSprite): { x: number; y: number } {
  const align = typeof stageSprite.params?.align === 'string'
    ? stageSprite.params.align.trim().toUpperCase()
    : 'CB';

  switch (align) {
    case 'LT':
      return { x: 0, y: 0 };
    case 'CT':
      return { x: 0.5, y: 0 };
    case 'RT':
      return { x: 1, y: 0 };
    case 'LM':
      return { x: 0, y: 0.5 };
    case 'CM':
      return { x: 0.5, y: 0.5 };
    case 'RM':
      return { x: 1, y: 0.5 };
    case 'LB':
      return { x: 0, y: 1 };
    case 'RB':
      return { x: 1, y: 1 };
    case 'CB':
    default:
      return { x: 0.5, y: 1 };
  }
}

function spriteRollRadiansFromParam(stageSprite: StageSprite): number {
  const roll = stageSprite.params?.roll;
  if (typeof roll !== 'number' || !Number.isFinite(roll)) {
    return 0;
  }

  return (-roll * Math.PI) / 180;
}

async function preloadStageSpriteTextures(data: StageDataV1): Promise<void> {
  const texturePaths = new Set<string>();

  for (const stageSprite of data.sprites) {
    texturePaths.add(selectSpriteTexturePath(stageSprite));
  }

  const results = await Promise.allSettled(
    [...texturePaths].map(async (texturePath) => {
      await Assets.load(texturePath);
      return texturePath;
    }),
  );

  for (const result of results) {
    if (result.status === 'rejected') {
      console.warn('[Stage] Failed to preload sprite texture', result.reason);
    }
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

function rotatePointInverse(
  point: { x: number; y: number; z: number },
  rotation: StageTrigger['rotation'],
): { x: number; y: number; z: number } {
  const yaw = (-rotation.yaw * Math.PI) / 180;
  const pitch = (-rotation.pitch * Math.PI) / 180;
  const roll = (-rotation.roll * Math.PI) / 180;

  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  const cosRoll = Math.cos(roll);
  const sinRoll = Math.sin(roll);

  const yawX = cosYaw * point.x - sinYaw * point.z;
  const yawZ = sinYaw * point.x + cosYaw * point.z;
  const yawY = point.y;

  const pitchY = cosPitch * yawY - sinPitch * yawZ;
  const pitchZ = sinPitch * yawY + cosPitch * yawZ;
  const pitchX = yawX;

  return {
    x: cosRoll * pitchX - sinRoll * pitchY,
    y: sinRoll * pitchX + cosRoll * pitchY,
    z: pitchZ,
  };
}

function isPointInsideTrigger(point: { x: number; y: number; z: number }, trigger: StageTrigger): boolean {
  const local = rotatePointInverse(
    {
      x: point.x - trigger.position.x,
      y: point.y - trigger.position.y,
      z: point.z - trigger.position.z,
    },
    trigger.rotation,
  );

  return (
    Math.abs(local.x) <= trigger.halfExtents.x &&
    Math.abs(local.y) <= trigger.halfExtents.y &&
    Math.abs(local.z) <= trigger.halfExtents.z
  );
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
  activeTriggerIds: Set<string>,
): void {
  graphics.clear();

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
    const isActive = activeTriggerIds.has(trigger.id);
    graphics.setStrokeStyle({
      width: isActive ? 2.5 : 1.5,
      color: isActive ? 0x66ffcc : 0xff6699,
      alpha: 0.95,
    });
    graphics.rect(projected.x - width / 2, projected.y - height / 2, width, height);
    graphics.stroke();
  }
}

function updateWaypointTravelSpeed(runtimeState: TriggerRuntimeState, dt: number): void {
  const transition = runtimeState.waypointTravelSpeedTransition;
  if (!transition.active) {
    return;
  }

  transition.elapsedMs += dt * 1000;
  const progress = transition.durationMs <= 0
    ? 1
    : Math.min(1, transition.elapsedMs / transition.durationMs);

  runtimeState.waypointTravelSpeed =
    transition.fromSpeed + (transition.toSpeed - transition.fromSpeed) * progress;

  if (progress >= 1) {
    transition.active = false;
    runtimeState.waypointTravelSpeed = transition.toSpeed;
  }
}

function updateTriggerOverlaps(
  triggers: StageTrigger[],
  camera: CameraPoint,
  overlapState: TriggerOverlapState,
  runtimeState: TriggerRuntimeState,
): void {
  const nextActiveTriggerIds = new Set<string>();

  for (const trigger of triggers) {
    if (isPointInsideTrigger(camera, trigger)) {
      nextActiveTriggerIds.add(trigger.id);
      const hasEnteredThisFrame = !overlapState.activeTriggerIds.has(trigger.id);
      const hasAlreadyFired = overlapState.firedTriggerIds.has(trigger.id);
      const shouldFire = hasEnteredThisFrame && (!trigger.once || !hasAlreadyFired);
      const normalizedEvent = trigger.event.trim().toLowerCase();

      if (shouldFire) {
        if (normalizedEvent === 'speed' || normalizedEvent === 'speed-change' || normalizedEvent === 'speedchange') {
          const speedParam = trigger.params?.speed;
          if (typeof speedParam === 'number' && Number.isFinite(speedParam)) {
            const durationMillisParam = trigger.params?.durationMillis;
            const hasDurationMillis =
              typeof durationMillisParam === 'number' &&
              Number.isFinite(durationMillisParam) &&
              durationMillisParam > 0;

            if (hasDurationMillis) {
              runtimeState.waypointTravelSpeedTransition = {
                active: true,
                elapsedMs: 0,
                durationMs: durationMillisParam,
                fromSpeed: runtimeState.waypointTravelSpeed,
                toSpeed: speedParam,
              };
            } else {
              runtimeState.waypointTravelSpeed = speedParam;
              runtimeState.waypointTravelSpeedTransition.active = false;
            }
          } else {
            console.warn('[Trigger] Ignored speed trigger without numeric params.speed', {
              id: trigger.id,
              event: trigger.event,
              params: trigger.params ?? {},
            });
          }
        }

        console.log('[Trigger] Enter', {
          id: trigger.id,
          event: trigger.event,
          once: trigger.once ?? false,
          waypointTravelSpeed: runtimeState.waypointTravelSpeed,
          camera: { x: camera.x, y: camera.y, z: camera.z },
          params: trigger.params ?? {},
        });
        overlapState.firedTriggerIds.add(trigger.id);
      }
    } else if (overlapState.activeTriggerIds.has(trigger.id)) {
      console.log('[Trigger] Exit', {
        id: trigger.id,
        event: trigger.event,
        camera: { x: camera.x, y: camera.y, z: camera.z },
      });
    }
  }

  overlapState.activeTriggerIds = nextActiveTriggerIds;
}

function makeStageSpriteInstances(
  app: Application,
  data: StageDataV1,
  config: ProjectionConfig,
): StageSpriteInstance[] {
  return data.sprites.map((stageSprite) => {
    const texturePath = selectSpriteTexturePath(stageSprite);
    const hasLoadedTexture = Assets.get(texturePath) !== undefined;
    const sprite = hasLoadedTexture
      ? Sprite.from(texturePath)
      : new Sprite(Texture.WHITE);
    sprite.texture.source.style.scaleMode = 'nearest';
    const anchor = spriteAnchorFromAlignParam(stageSprite);
    sprite.anchor.set(anchor.x, anchor.y);
    sprite.tint = colorForStageSprite(stageSprite);
    sprite.alpha = 1.0;
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
      rollRadians: spriteRollRadiansFromParam(stageSprite),
      sprite,
    };
  });
}

function updateStageSprites(
  instances: StageSpriteInstance[],
  camera: CameraPoint,
  config: ProjectionConfig,
): number {
  let visibleSpriteCount = 0;

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
    visibleSpriteCount += 1;
    instance.sprite.x = projected.x;
    instance.sprite.y = projected.y;
    const spriteScale = config.focalX / projected.z;
    instance.sprite.width = Math.max(1, instance.worldWidth * spriteScale);
    instance.sprite.height = Math.max(1, instance.worldHeight * spriteScale);
    instance.sprite.rotation = instance.rollRadians;
    instance.sprite.zIndex = -projected.z;
  }

  return visibleSpriteCount;
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
  await preloadStageSpriteTextures(data);

  const colliderGraphics = makeVolumeGraphics(0xffcc33);
  const triggerGraphics = makeVolumeGraphics(0xff6699);

  app.stage.addChild(colliderGraphics);
  app.stage.addChild(triggerGraphics);

  const spriteInstances = makeStageSpriteInstances(app, data, config);
  const waypointPath = buildWaypointPath(data.waypoints);
  let waypointTravelDistance = 0;
  const triggerOverlapState: TriggerOverlapState = {
    activeTriggerIds: new Set<string>(),
    firedTriggerIds: new Set<string>(),
  };
  const triggerRuntimeState: TriggerRuntimeState = {
    waypointTravelSpeed: 1,
    waypointTravelSpeedTransition: {
      active: false,
      elapsedMs: 0,
      durationMs: 0,
      fromSpeed: 1,
      toSpeed: 1,
    },
  };
  let camera: CameraPoint = data.waypoints[0]
    ? { ...data.waypoints[0].position, yaw: 0 }
    : { x: 0, y: 0, z: 0, yaw: 0 };

  return {
    data,
    update(dt: number) {
      const frameStart = performance.now();

      const cameraStart = performance.now();
      updateWaypointTravelSpeed(triggerRuntimeState, dt);
      waypointTravelDistance += triggerRuntimeState.waypointTravelSpeed * dt;
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
      const cameraMs = performance.now() - cameraStart;

      const spritesStart = performance.now();
      const visibleSpriteCount = updateStageSprites(spriteInstances, camera, config);
      const spritesMs = performance.now() - spritesStart;

      const collidersStart = performance.now();
      drawColliderVolumes(colliderGraphics, data.colliders, camera, config);
      const collidersMs = performance.now() - collidersStart;

      const triggersStart = performance.now();
      updateTriggerOverlaps(data.triggers, camera, triggerOverlapState, triggerRuntimeState);
      drawTriggerVolumes(triggerGraphics, data.triggers, camera, config, triggerOverlapState.activeTriggerIds);
      const triggersMs = performance.now() - triggersStart;

      return {
        totalMs: performance.now() - frameStart,
        cameraMs,
        spritesMs,
        visibleSpriteCount,
        collidersMs,
        triggersMs,
      };
    },
  };
}
