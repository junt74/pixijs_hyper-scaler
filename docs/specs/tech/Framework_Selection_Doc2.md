# フレームワーク選定：レンダリング・物理エンジン以外の領域

> 対象：PixiJS（レンダリング）・cannon-es（物理）以外のサブシステムのライブラリ・実装方針選定。

---

## 1. 入力（Input）

キーボードとゲームパッドの両方に対応する必要がある。Galaxy Forceスタイルの操作感にはアナログ入力が重要。

**選択肢：**

| 方式 | 概要 | 備考 |
| --- | --- | --- |
| ブラウザネイティブ | `KeyboardEvent` + `Gamepad API` 直接使用 | 依存ゼロ。デッドゾーン処理を自前実装 |
| ラッパーライブラリ | `gamepad.js` 等の薄いラッパー | 依存追加の割にメリット小 |

**検討事項：**

- アナログスティックのデッドゾーン処理（入力がゼロ付近でふらつかないための閾値）
- キーボードはデジタル入力（-1 / 0 / +1）のため、アナログ入力と正規化が必要
- ゲームパッドのボタンマッピング（Xboxレイアウト等への対応）

### 方針（確定）：ブラウザネイティブ + InputManager 抽象化

- ライブラリは使用しない。`KeyboardEvent` + `Gamepad API` を直接使用する。
- `InputManager` クラスで抽象化し、ゲームロジックは `InputState` インターフェースのみを参照する。
- ゲームパッドが接続されていて入力がある場合に優先。それ以外はキーボードにフォールバック。

#### InputState インターフェース

```text
// 軸入力（正規化済み -1.0 〜 +1.0）
ax  : number   // 水平軸  負=左, 正=右
ay  : number   // 垂直軸  負=上, 正=下

// ボタン（押し続け判定）
shot    : boolean   // メインショット（ホールドで連射）
missile : boolean   // ミサイル（ホールドで連続発射）
pause   : boolean   // ポーズ

// ボタン（押した瞬間のみ true：エッジ検出）
shotPressed    : boolean
missilePressed : boolean
pausePressed   : boolean
confirmPressed : boolean   // メニュー確定
cancelPressed  : boolean   // メニューキャンセル
```

#### デバイス別マッピング

| アクション | ゲームパッド（Standardレイアウト） | キーボード |
| --- | --- | --- |
| 水平軸 | `axes[0]`（左スティック） | `←` / `→`、`A` / `D` |
| 垂直軸 | `axes[1]`（左スティック） | `↑` / `↓`、`W` / `S` |
| ショット | `buttons[0]`（A / ×） | `Z`、`Space` |
| ミサイル | `buttons[2]`（X / □） | `X`、`LeftShift` |
| ポーズ | `buttons[9]`（Start） | `Escape`、`P` |
| 確定 | `buttons[0]`（A / ×） | `Enter`、`Z` |
| キャンセル | `buttons[1]`（B / ○） | `Escape`、`X` |

#### チューニング定数

```text
DEADZONE      = 0.12   // この値未満の入力はゼロとみなす
DEADZONE_RESCALE = true  // デッドゾーン除去後に 0〜1 に再スケールする
```

デッドゾーン補正式：

```text
補正後 = (|v| - DEADZONE) / (1 - DEADZONE) × sign(v)
```

#### キーボード対角入力の正規化

```text
ax, ay を計算後、ベクトル長が 1.0 を超える場合は単位ベクトルに正規化する
（斜め移動がアナログ斜め入力より速くならないようにする）
```

#### Gamepad APIの注意事項

- `navigator.getGamepads()` はイベント駆動ではない。毎フレームのゲームループ内でpollingする。
- ゲームパッドのY軸（`axes[1]`）は上方向が `-1`。`ay` への代入時に符号は確認・統一すること。

---

## 2. オーディオ（Audio）

BGMとSEを扱う。空間オーディオは不要（2Dスプライト表現のため）。

**選択肢：**

| ライブラリ | 概要 | 備考 |
| --- | --- | --- |
| **Howler.js** | Web Audio APIラッパー。BGM・SE・AudioSprite対応。実績多数 | デファクトスタンダード |
| @pixi/sound | PixiJS公式プラグイン | 機能はHowlerより少ない |
| Web Audio API直接 | 最大の制御性 | ボイラープレートが多い |

**検討事項：**

- AudioSprite（1ファイルに複数SEを収録）でHTTPリクエスト数を削減できる
- BGMのシームレスループ対応
- ブラウザのAutoplay Policy対策（最初のユーザー操作後に再生開始）

### 方針（確定）：Howler.js を採用

- BGM・SEともにHowler.jsで管理する。PixiJS Assetsとは独立してHowler側でロードする。
- SEは**AudioSprite**方式（1ファイルに全SE収録）でHTTPリクエスト数を最小化する。
- BGMは `loop: true` でシームレスループ。フェードイン・アウトはHowler組み込みの `fade()` を使用する。
- Autoplay Policy対策：Howler.jsはユーザー操作前の再生を自動的にキューイングし、最初のインタラクション後に再生を開始する（`Howler.autoUnlock` がデフォルトで有効）。

#### 使用パターン

```text
BGM : new Howl({ src: ['bgm_stage1.ogg', 'bgm_stage1.mp3'], loop: true })
SE  : new Howl({ src: ['se.ogg'], sprite: {
        shot:     [0,    200],   // 0ms〜200ms
        explosion:[200,  800],   // 200ms〜1000ms
        ...
      }})
```

#### 注意事項

- オーディオファイルは `.ogg`（第1候補）と `.mp3`（フォールバック）の2形式を用意する。
- SEのAudioSprite区間設計はアセット制作時に確定させる（後から変更するとオフセットがずれる）。

---

## 3. アセットローダー（Asset Loader）

テクスチャアトラス・JSON・音声などのアセットをまとめてロードする仕組み。

**選択肢：**

| 方式 | 概要 | 備考 |
| --- | --- | --- |
| **PixiJS Assets**（組み込み） | v7以降に標準搭載。Promise API。テクスチャ・Atlas・JSONに対応 | 追加依存ゼロ |
| カスタムローダー | 自前実装 | 特殊要件がない限り不要 |

**検討事項：**

- 音声ファイルはPixiJS Assetsの管轄外。Howler.js側でロードする
- プログレス表示（ロード画面）の実装はPixiJS Assets の進捗イベントで対応可

### 方針（確定）：PixiJS Assets（テクスチャ・アトラス・JSON）+ Howler.js（音声）の役割分担

- テクスチャ、テクスチャアトラス、ステージJSONはPixiJS Assetsでロードする。
- 音声（BGM・SE）はHowler.jsが独自にロードする。PixiJS Assetsを経由しない。
- ロード進捗表示はPixiJS Assetsの `onProgress` コールバックで実装する（音声は別途Howlerのコールバックで対応）。

---

## 4. シーン・ゲームステート管理

タイトル・ゲームプレイ・ポーズ・ゲームオーバーなどの画面遷移と状態管理。

**選択肢：**

| 方式 | 概要 | 備考 |
| --- | --- | --- |
| カスタムステートマシン | 列挙型 + enter/update/exit フックの自前実装 | 小規模には十分 |
| XState | 本格的な有限状態機械ライブラリ | このスケールでは過剰 |

**検討事項：**

- 想定シーン：`Title` → `StageSelect` → `Gameplay` → `Pause` → `GameOver` → `Ranking`
- 遷移数は限られており、カスタム実装で十分に対応可能

### 方針（確定）：カスタムステートマシン（独自実装）

- XStateは使用しない。列挙型 + `enter` / `update` / `exit` フックの自前実装とする。
- 各シーンはクラスまたはオブジェクトとして実装し、`SceneManager` が現在シーンの `update` を毎フレーム呼び出す。
- 想定シーン：`Title` → `StageSelect` → `Gameplay` ⇄ `Pause` → `GameOver` → `Ranking`

---

## 5. タイマー・コルーチン

カットシーン演出・時限イベントの実装に使用。

**選択肢：**

| 方式 | 概要 |
| --- | --- |
| `async / await` + `setTimeout` | ネイティブ。カットシーンの逐次処理に自然に書ける |
| カスタムタイマーキュー | fixedUpdateと同期させたい場合に有効 |

**検討事項：**

- `setTimeout` は物理ステップと非同期。ゲームロジックに影響するタイマーはFixed Timestepループ内で処理するほうが安全

### 方針（確定）：用途で使い分け

- **演出・カットシーン**（ゲームロジックに影響しない）：`async/await` + `setTimeout` で逐次記述する。
- **ゲームロジックに影響するタイマー**（無敵時間・リスポーン待機など）：Fixed Timestepループ内でフレームカウンターを使って管理する。`setTimeout` は使わない。

---

## 6. セーブデータ

ハイスコア・設定などの永続化。

**選択肢：**

| 方式 | 概要 | 備考 |
| --- | --- | --- |
| `localStorage` | キー・バリュー形式。同期API | アーケードゲームの用途には十分 |
| `IndexedDB` | 大容量・非同期。構造化データ対応 | このスケールでは過剰 |

### 方針（確定）：localStorage を使用

- `localStorage` にJSON文字列としてシリアライズして保存する。
- 保存対象：ハイスコア、音量設定、キーコンフィグ。
- `SaveManager` クラスに集約し、直接 `localStorage` を触るコードをゲームロジックに書かない。

---

*作成日：2026-03-11*
