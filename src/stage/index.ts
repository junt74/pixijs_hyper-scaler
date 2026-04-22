export {
  parseStageData,
  STAGE_FORMAT_VERSION,
  validateStageData,
} from './schema';

export type {
  Rotation3,
  StageCollider,
  StageDataV1,
  StageFormatVersion,
  StageMeta,
  StageSourceInfo,
  StageSprite,
  StageTrigger,
  StageValidationResult,
  StageWaypoint,
  Vec3,
} from './schema';

export { loadStage } from './loader';
export type { LoadedStage, StageUpdateProfile } from './loader';
