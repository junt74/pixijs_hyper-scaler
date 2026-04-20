# PixiJS Hyper Scaler Blender Exporter

`stage.json` v1 を Blender から出力するための最小アドオンです。

## 現在の対象

- `Waypoints` collection
- `Colliders` collection
- `Sprites` root collection
- `Triggers` collection

## Blender 側の作り方

### 1. Waypoints

- `Waypoints` という Collection を作る
- その中に Empty などのオブジェクトを順番に置く
- 配列順はオブジェクト名の昇順で決まるため、`WP_000`, `WP_010` のように命名する

### 2. Colliders

- `Colliders` Collection 内に Box collider 用オブジェクトを置く
- 出力はすべて `type: "box"`
- `halfExtents` はオブジェクトの `dimensions / 2` から計算する
- 必要なら custom property `layer` を付ける

### 3. Sprites

- `Sprites` を親 Collection にする
- 子 Collection 名が `sprites[*].type` になる
- 各子 Collection に Empty などの配置オブジェクトを置く
- 追加の custom property は `params` に入る

例:

- `Sprites/EnemyA/*` -> `type: "EnemyA"`
- `Sprites/Tree/*` -> `type: "Tree"`

### 4. Triggers

- `Triggers` Collection にトリガーオブジェクトを置く
- 各オブジェクトに string の custom property `event` を付ける
- それ以外の単純な custom property は `params` に入る

例:

- `event = "Checkpoint"`
- `event = "SpeedChange"` and `speed = 120`

## Scene custom properties

Scene に以下を持たせるとトップレベルに反映されます。

- `stage_id`
- `stage_name`

未設定なら Scene 名から生成します。

## インストール

1. Blender で `Edit > Preferences > Add-ons > Install...`
2. このフォルダを zip にして選ぶか、`__init__.py` を含むフォルダを指定する
3. `PixiJS Hyper Scaler Stage Exporter` を有効化する

## 使い方

### File メニュー

- `File > Export > PixiJS Hyper Scaler Stage (.json)`

### 3D View

- サイドバーの `HyperScaler` タブから export

## 制限

- Waypoints は現時点では Curve 等間隔サンプリングではなく Collection 内オブジェクト列です
- Collider / Trigger shape は box のみです
- 回転変換は v1 の簡易マッピングです
- object custom property は string / number / boolean のみ出力します

次の段階では、Curve からの waypoint サンプリング、より厳密な回転変換、エクスポート前バリデーション強化を追加する想定です。
