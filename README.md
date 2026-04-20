# pixijs-hyper-scaler

SEGA Y-BOARD, SYSTEM 32の表現をPixiJS + cannon-es を用いて行う、ブラウザ動作の **Super Scaler ゲームエンジン** プロトタイプ。

Galaxy Force スタイルの自動前進レールシューターを想定した設計・実装を行う。

---

## 技術スタック

| 役割 | ライブラリ |
| --- | --- |
| レンダリング（2Dスプライト投影） | PixiJS |
| 物理演算 | cannon-es |
| オーディオ | Howler.js |
| 入力 | ブラウザネイティブ（Gamepad API / KeyboardEvent） |
| アセットロード | 画像はPixiJS Assets, 音声はHowler.js |

---

## アーキテクチャ概要

- cannon-es で物理ボディを管理し、毎フレームの World→Camera 透視投影でスプライトを描画する（疑似3D不使用）
- Fixed Timestep + 線形補間により物理と描画を分離
- ステージデータ（コライダー・スプライト配置・ウェイポイント・トリガー）は Blender で制作し JSON にエクスポート

---

## ドキュメント

設計方針・技術的課題の整理は `docs/specs/tech/` を参照。

| ファイル | 内容 |
| --- | --- |
| [Technical_Challenges_True3D_Doc1.md](docs/specs/tech/Technical_Challenges_True3D_Doc1.md) | 真3Dエンジンの技術的課題と確定方針（物理・レンダリング・Blenderエクスポート） |
| [Framework_Selection_Doc2.md](docs/specs/tech/Framework_Selection_Doc2.md) | レンダリング・物理以外のサブシステムのライブラリ選定（入力・オーディオ・シーン管理など） |
| [Stage_JSON_Schema_Doc3.md](docs/specs/tech/Stage_JSON_Schema_Doc3.md) | DCC から出力する `stage.json` の初版スキーマ定義（waypoints / colliders / sprites / triggers） |
| [Near_Term_Roadmap_Doc4.md](docs/specs/milestones/Near_Term_Roadmap_Doc4.md) | エンジン実装 / Blender AddOn / 人手制作の3視点で整理した直近ロードマップ |

Blender エクスポーターの最小実装は [tools/blender_addons/pixijs_hyper_scaler_stage_exporter](/Users/junt74/Projects/PixiJS/pixijs_hyper-scaler/tools/blender_addons/pixijs_hyper_scaler_stage_exporter) にあります。サンプル JSON は [public/assets/stages/sample-stage.json](/Users/junt74/Projects/PixiJS/pixijs_hyper-scaler/public/assets/stages/sample-stage.json) を参照してください。
