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
- 各子 Collection には通常 sprite 用に `Empty` を置く
- 通常 sprite の `Display As` は `Plain Axes` を使う
- `CURVE` object も置ける
- 通常 sprite / Curve Sprite ともに `Anchor` を `LT/CT/RT/LM/CM/RM/LB/CB/RB` から選べる
- 追加の custom property は `params` に入る
- 通常 sprite object には `Sprite Array` を設定できる
- Blender 5 の新しい Geometry Nodes ベース `Array` を含む modifier 評価結果から、JSON 上で複製展開される
- 従来の `Array` modifier は手動展開にも対応している
- 同一オブジェクト内の複数 `Array` modifier / 多重配列も扱える
- `CURVE` は `Curve Sprite` 設定を有効にすると、等間隔に `sprites[]` へ展開される
- `Curve Sprite` には中心基準の `X Replication` があり、1 本の Curve から床板の横並びを作れる
- 現在の従来 `Array` 手動展開の対応は `Fixed Count` のみ

例:

- `Sprites/EnemyA/*` -> `type: "EnemyA"`
- `Sprites/Tree/*` -> `type: "Tree"`

### 3.1 Sprite Array

- `Sprites/<type>/` 配下の通常 `Empty` object を選択
- `3D View > Sidebar > HyperScaler > Sprite Array` を開く
- `Enabled` をオンにする
- `Anchor` で、配置点に対してスプライトのどの位置を合わせるかを選ぶ
- `Grid Count X/Y/Z` と `Grid Step X/Y/Z` を設定する
- 必要なら `Center On Base` の X/Y/Z を個別にオンにして、基準位置を中心に複製する
- 配置は常に XYZ 軸に揃った直交格子として扱われる
- active object については 3D View にラインとマーカーでプレビューが表示される
- export 時にはその配置が `sprites[]` へ展開される

### 3.2 Curve Sprite

- `Sprites/<type>/` 配下の `CURVE` object を選択
- `3D View > Sidebar > HyperScaler > Curve Sprite` を開く
- `Enabled` をオンにする
- `Anchor` で、各配置点に対してスプライトのどの位置を合わせるかを選ぶ
- `Spacing` で配置間隔を決める
- `X Replication` の `Count` と `Step` で、各サンプル点を Curve のローカル X 方向へ中心対称に複製できる
- 必要なら `Start Offset` / `End Inset` / `Local Offset` を設定する
- billboard 前提のため `yaw` は `0` で export される

### 4. Triggers

- `Triggers` Collection に `Empty` を置く
- `Empty` の `Display As` は `Sphere` を使う
- `Radius` と object scale から `halfExtents` が計算される
- 推奨: `3D View > Sidebar > HyperScaler > Trigger` から編集する
- `Trigger` パネルから `Display As` と `Radius` も確認できる
- `Event` はドロップダウンで選べる。`speed-change` や `checkpoint`、必要なら `Custom` も使える
- `Once` に加えて `speed` / `durationMillis` を型付き UI で設定できる
- `Params JSON` は追加パラメータや上級者向けの直接編集に使える
- 後方互換として、各オブジェクトまたはその Mesh data に custom property を付けても export できる
- object と Mesh data の両方に同名 property がある場合は object 側を優先する
- `Params JSON` を使わない場合は、予約語以外の単純な custom property が `params` に入る
- 型付き UI で設定した値は、同じキーが `Params JSON` にあってもそちらを上書きする

例:

- `event = "checkpoint"`
- `event = "speed.change"`, `once = true`, `params = {"speed": 2}`

## Scene custom properties

Scene に以下を持たせるとトップレベルに反映されます。

- `stage_id`
- `stage_name`

未設定なら Scene 名から生成します。

## インストール

最も確実なのは、単一ファイル版を入れる方法です。

1. Blender で `Edit > Preferences > Add-ons > Install...`
2. [tools/blender_addons/pixijs_hyper_scaler_stage_exporter.py](/Users/junt74/Projects/PixiJS/pixijs_hyper-scaler/tools/blender_addons/pixijs_hyper_scaler_stage_exporter.py) を選ぶ
3. 一覧で `PixiJS Hyper Scaler Stage Exporter` を検索して有効化する

zip で入れる場合は、zip の直下に `__init__.py` がある構造にする。
つまり `pixijs_hyper_scaler_stage_exporter/` フォルダをそのまま zip にする。

やってはいけない例:

- `tools/` ごと zip する
- `blender_addons/` ごと zip する
- フォルダをそのまま選ぶ

## 使い方

### File メニュー

- `File > Export > PixiJS Hyper Scaler Stage (.json)`

### 3D View

- サイドバーの `HyperScaler` タブから export
- `Sprite Diagnostics` をオンにすると、`source.spriteExportDiagnostics` を JSON に含める
- `Trigger` パネルで trigger 用の `Event / Once / Params JSON` を編集できる
- `Trigger` パネルで `Event` ドロップダウンと `speed` / `durationMillis` を直接編集できる
- `Sprite Array` パネルで通常 sprite object の反復配置とプレビューを設定できる
- 通常 sprite object は `Empty + Plain Axes` を前提にしている
- `Curve Sprite` パネルで curve から sprite を並べる設定ができる

## 制限

- Waypoints は現時点では Curve 等間隔サンプリングではなく Collection 内オブジェクト列です
- Collider は box のみ、Trigger は Empty Sphere から box volume として出力します
- 回転変換は v1 の簡易マッピングです
- object custom property は string / number / boolean のみ出力します
- 従来 `Array` modifier の手動展開は `Fixed Count` のみ対応です
- `Sprite Array` の 3D View プレビューは active object のみ表示します
- `Curve Sprite` は評価後メッシュの折れ線を元にサンプリングするため、複雑な curve 設定では意図と差が出る場合があります
- `Array` の複製数は安全のため 65536 件までに制限しています
- `source.spriteExportDiagnostics` はデバッグ用途で、必要な時だけ有効化する想定です

次の段階では、Curve からの waypoint サンプリング、より厳密な回転変換、エクスポート前バリデーション強化、
さらに Trigger の `Event` 種類に応じて `params` UI の内容を切り替える対応を追加する想定です。
