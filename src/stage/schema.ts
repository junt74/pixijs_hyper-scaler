export const STAGE_FORMAT_VERSION = 1 as const;

export type StageFormatVersion = typeof STAGE_FORMAT_VERSION;

export type Vec3 = {
  x: number;
  y: number;
  z: number;
};

export type Rotation3 = {
  yaw: number;
  pitch: number;
  roll: number;
};

export type StageSourceInfo = {
  dcc?: string;
  scene?: string;
};

export type StageMeta = {
  exportedAt?: string;
  [key: string]: unknown;
};

export type StageWaypoint = {
  id: string;
  position: Vec3;
};

export type StageCollider = {
  id: string;
  name?: string;
  type: 'box';
  position: Vec3;
  rotation: Rotation3;
  halfExtents: Vec3;
  layer?: string;
};

export type StageSprite = {
  id: string;
  name?: string;
  type: string;
  position: Vec3;
  yaw: number;
  params?: Record<string, unknown>;
};

export type StageTrigger = {
  id: string;
  name?: string;
  event: string;
  position: Vec3;
  rotation: Rotation3;
  halfExtents: Vec3;
  params?: Record<string, unknown>;
};

export type StageDataV1 = {
  formatVersion: StageFormatVersion;
  stageId: string;
  name?: string;
  source?: StageSourceInfo;
  meta?: StageMeta;
  waypoints: StageWaypoint[];
  colliders: StageCollider[];
  sprites: StageSprite[];
  triggers: StageTrigger[];
};

export type StageValidationResult =
  | { ok: true; data: StageDataV1 }
  | { ok: false; errors: string[] };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isVec3(value: unknown): value is Vec3 {
  return (
    isObject(value) &&
    isFiniteNumber(value.x) &&
    isFiniteNumber(value.y) &&
    isFiniteNumber(value.z)
  );
}

function isRotation3(value: unknown): value is Rotation3 {
  return (
    isObject(value) &&
    isFiniteNumber(value.yaw) &&
    isFiniteNumber(value.pitch) &&
    isFiniteNumber(value.roll)
  );
}

function isStringRecord(value: unknown): value is Record<string, unknown> {
  return isObject(value);
}

function pushError(errors: string[], path: string, message: string): void {
  errors.push(`${path}: ${message}`);
}

function validateWaypoint(
  value: unknown,
  index: number,
  errors: string[],
): value is StageWaypoint {
  const path = `waypoints[${index}]`;
  const beforeErrorCount = errors.length;
  if (!isObject(value)) {
    pushError(errors, path, 'must be an object');
    return false;
  }
  if (!isNonEmptyString(value.id)) {
    pushError(errors, `${path}.id`, 'must be a non-empty string');
  }
  if (!isVec3(value.position)) {
    pushError(errors, `${path}.position`, 'must be a Vec3');
  }
  return errors.length === beforeErrorCount;
}

function validateCollider(
  value: unknown,
  index: number,
  errors: string[],
): value is StageCollider {
  const path = `colliders[${index}]`;
  const beforeErrorCount = errors.length;
  if (!isObject(value)) {
    pushError(errors, path, 'must be an object');
    return false;
  }
  if (!isNonEmptyString(value.id)) {
    pushError(errors, `${path}.id`, 'must be a non-empty string');
  }
  if (value.name !== undefined && typeof value.name !== 'string') {
    pushError(errors, `${path}.name`, 'must be a string when present');
  }
  if (value.type !== 'box') {
    pushError(errors, `${path}.type`, 'must be "box"');
  }
  if (!isVec3(value.position)) {
    pushError(errors, `${path}.position`, 'must be a Vec3');
  }
  if (!isRotation3(value.rotation)) {
    pushError(errors, `${path}.rotation`, 'must be a Rotation3');
  }
  if (!isVec3(value.halfExtents)) {
    pushError(errors, `${path}.halfExtents`, 'must be a Vec3');
  } else if (value.halfExtents.x <= 0 || value.halfExtents.y <= 0 || value.halfExtents.z <= 0) {
    pushError(errors, `${path}.halfExtents`, 'all components must be greater than 0');
  }
  if (value.layer !== undefined && typeof value.layer !== 'string') {
    pushError(errors, `${path}.layer`, 'must be a string when present');
  }
  return errors.length === beforeErrorCount;
}

function validateSprite(
  value: unknown,
  index: number,
  errors: string[],
): value is StageSprite {
  const path = `sprites[${index}]`;
  const beforeErrorCount = errors.length;
  if (!isObject(value)) {
    pushError(errors, path, 'must be an object');
    return false;
  }
  if (!isNonEmptyString(value.id)) {
    pushError(errors, `${path}.id`, 'must be a non-empty string');
  }
  if (value.name !== undefined && typeof value.name !== 'string') {
    pushError(errors, `${path}.name`, 'must be a string when present');
  }
  if (!isNonEmptyString(value.type)) {
    pushError(errors, `${path}.type`, 'must be a non-empty string');
  }
  if (!isVec3(value.position)) {
    pushError(errors, `${path}.position`, 'must be a Vec3');
  }
  if (!isFiniteNumber(value.yaw)) {
    pushError(errors, `${path}.yaw`, 'must be a finite number');
  }
  if (value.params !== undefined && !isStringRecord(value.params)) {
    pushError(errors, `${path}.params`, 'must be an object when present');
  }
  return errors.length === beforeErrorCount;
}

function validateTrigger(
  value: unknown,
  index: number,
  errors: string[],
): value is StageTrigger {
  const path = `triggers[${index}]`;
  const beforeErrorCount = errors.length;
  if (!isObject(value)) {
    pushError(errors, path, 'must be an object');
    return false;
  }
  if (!isNonEmptyString(value.id)) {
    pushError(errors, `${path}.id`, 'must be a non-empty string');
  }
  if (value.name !== undefined && typeof value.name !== 'string') {
    pushError(errors, `${path}.name`, 'must be a string when present');
  }
  if (!isNonEmptyString(value.event)) {
    pushError(errors, `${path}.event`, 'must be a non-empty string');
  }
  if (!isVec3(value.position)) {
    pushError(errors, `${path}.position`, 'must be a Vec3');
  }
  if (!isRotation3(value.rotation)) {
    pushError(errors, `${path}.rotation`, 'must be a Rotation3');
  }
  if (!isVec3(value.halfExtents)) {
    pushError(errors, `${path}.halfExtents`, 'must be a Vec3');
  } else if (value.halfExtents.x <= 0 || value.halfExtents.y <= 0 || value.halfExtents.z <= 0) {
    pushError(errors, `${path}.halfExtents`, 'all components must be greater than 0');
  }
  if (value.params !== undefined && !isStringRecord(value.params)) {
    pushError(errors, `${path}.params`, 'must be an object when present');
  }
  return errors.length === beforeErrorCount;
}

function validateUniqueIds(stage: StageDataV1, errors: string[]): void {
  const seen = new Set<string>();
  const items: Array<{ kind: string; id: string }> = [
    ...stage.waypoints.map((item) => ({ kind: 'waypoints', id: item.id })),
    ...stage.colliders.map((item) => ({ kind: 'colliders', id: item.id })),
    ...stage.sprites.map((item) => ({ kind: 'sprites', id: item.id })),
    ...stage.triggers.map((item) => ({ kind: 'triggers', id: item.id })),
  ];

  for (const item of items) {
    if (seen.has(item.id)) {
      pushError(errors, item.kind, `duplicate id "${item.id}"`);
      continue;
    }
    seen.add(item.id);
  }
}

export function validateStageData(value: unknown): StageValidationResult {
  const errors: string[] = [];

  if (!isObject(value)) {
    return { ok: false, errors: ['stage: must be an object'] };
  }

  if (value.formatVersion !== STAGE_FORMAT_VERSION) {
    pushError(errors, 'formatVersion', `must be ${STAGE_FORMAT_VERSION}`);
  }
  if (!isNonEmptyString(value.stageId)) {
    pushError(errors, 'stageId', 'must be a non-empty string');
  }
  if (value.name !== undefined && typeof value.name !== 'string') {
    pushError(errors, 'name', 'must be a string when present');
  }
  if (value.source !== undefined && !isObject(value.source)) {
    pushError(errors, 'source', 'must be an object when present');
  }
  if (value.meta !== undefined && !isObject(value.meta)) {
    pushError(errors, 'meta', 'must be an object when present');
  }

  if (!Array.isArray(value.waypoints)) {
    pushError(errors, 'waypoints', 'must be an array');
  }
  if (!Array.isArray(value.colliders)) {
    pushError(errors, 'colliders', 'must be an array');
  }
  if (!Array.isArray(value.sprites)) {
    pushError(errors, 'sprites', 'must be an array');
  }
  if (!Array.isArray(value.triggers)) {
    pushError(errors, 'triggers', 'must be an array');
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  const formatVersion = value.formatVersion;
  const stageId = value.stageId;
  const name = value.name;
  const source = value.source;
  const meta = value.meta;
  const waypoints = value.waypoints;
  const colliders = value.colliders;
  const sprites = value.sprites;
  const triggers = value.triggers;

  if (
    formatVersion !== STAGE_FORMAT_VERSION ||
    !isNonEmptyString(stageId) ||
    !Array.isArray(waypoints) ||
    !Array.isArray(colliders) ||
    !Array.isArray(sprites) ||
    !Array.isArray(triggers)
  ) {
    return { ok: false, errors: ['stage: validation preconditions were not satisfied'] };
  }

  for (const [index, item] of waypoints.entries()) {
    validateWaypoint(item, index, errors);
  }
  for (const [index, item] of colliders.entries()) {
    validateCollider(item, index, errors);
  }
  for (const [index, item] of sprites.entries()) {
    validateSprite(item, index, errors);
  }
  for (const [index, item] of triggers.entries()) {
    validateTrigger(item, index, errors);
  }

  if (waypoints.length < 2) {
    pushError(errors, 'waypoints', 'must contain at least 2 items');
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  const data: StageDataV1 = {
    formatVersion,
    stageId,
    name: typeof name === 'string' ? name : undefined,
    source: isObject(source) ? source : undefined,
    meta: isObject(meta) ? meta : undefined,
    waypoints,
    colliders,
    sprites,
    triggers,
  };

  validateUniqueIds(data, errors);

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  return { ok: true, data };
}

export function parseStageData(value: unknown): StageDataV1 {
  const result = validateStageData(value);
  if (!result.ok) {
    throw new Error(`Invalid stage data:\n- ${result.errors.join('\n- ')}`);
  }
  return result.data;
}
