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
