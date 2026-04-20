# Stage JSON スキーマ設計（Doc3）

> 対象: Blender などの DCC からエクスポートされ、エンジンが直接ロードするステージデータの初版スキーマ定義。

---

## 1. 目的

このドキュメントでは、`stage.json` の **初版フォーマット** を定義する。

狙いは次の3点。

- DCC 側が「何を出力すべきか」を固定する
- エンジン側が「何を期待して読み込むか」を固定する
- 将来の拡張を見越しつつ、初版では最小限の構造に絞る

初版では以下の4カテゴリのみを扱う。

- `waypoints`
- `colliders`
- `sprites`
- `triggers`

---

## 2. 設計原則

### 2.1 初版は人間が読める JSON を優先する

- バイナリ化や圧縮は行わない
- 数値やカテゴリ名はデバッグしやすい形で保持する
- エクスポート結果を Git 管理・差分確認しやすくする

### 2.2 DCC の見た目データとゲーム意味論を分離する

- 見た目メッシュそのものは初版 `stage.json` に含めない
- 含めるのはゲームで必要な配置情報と属性のみ
- メッシュやテクスチャ参照は別のアセットパイプラインで管理する

### 2.3 Transform は可能な限り DCC の最終ワールド値を使う

- Export 時点で親子階層やモディファイア適用後のワールド値へ解決する
- エンジン側では再解釈せず、ほぼそのまま使えることを目標にする

### 2.4 型と責務を明確に分ける

- `type` はゲームロジック上の意味を表す
- `id` は一意識別子として使う
- `name` はデバッグ用の人間可読ラベルとして使う

---

## 3. 座標系・単位系

初版の `stage.json` は **エンジン座標系に変換済み** の値を保持する。
つまり、Blender 座標をそのまま保存するのではなく、エクスポーターが変換してから出力する。

### 3.1 エンジン座標系

- 右方向: `+X`
- 上方向: `+Y`
- 前方向: `+Z`

### 3.2 Blender からの変換ルール

| Blender | Engine |
| --- | --- |
| `X` | `X` |
| `Z` | `Y` |
| `Y` | `Z` |

前後軸の符号反転が必要かは、エクスポータ実装時に一度だけ確定し、以後は不変とする。
`stage.json` 側では変換済み結果のみを扱う。

### 3.3 単位

- 長さ単位はエンジンワールド単位で統一する
- 角度は **度数法** で保存する
- スケール値は出力しない。必要な形に正規化して出力する

初版では回転値はすべて次のキーで表す。

- `yaw`
- `pitch`
- `roll`

---

## 4. トップレベル構造

### 4.1 必須キー

- `formatVersion`
- `stageId`
- `waypoints`
- `colliders`
- `sprites`
- `triggers`

### 4.2 任意キー

- `name`
- `source`
- `meta`

### 4.3 例

```json
{
  "formatVersion": 1,
  "stageId": "stage01",
  "name": "Green Planet",
  "source": {
    "dcc": "Blender",
    "scene": "stage01.blend"
  },
  "meta": {
    "exportedAt": "2026-04-20T12:00:00Z"
  },
  "waypoints": [],
  "colliders": [],
  "sprites": [],
  "triggers": []
}
```

### 4.4 トップレベル項目

| キー | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
| `formatVersion` | number | 必須 | JSON スキーマのバージョン。初版は `1` 固定 |
| `stageId` | string | 必須 | ステージの論理 ID |
| `name` | string | 任意 | 人間向け表示名 |
| `source` | object | 任意 | DCC 由来の追跡情報 |
| `meta` | object | 任意 | 補助メタ情報 |
| `waypoints` | array | 必須 | レール用の経路点列 |
| `colliders` | array | 必須 | 静的コライダー |
| `sprites` | array | 必須 | スプライトエンティティ初期配置 |
| `triggers` | array | 必須 | イベント発火用ボリューム |

---

## 5. 共通プリミティブ

### 5.1 Vec3

```json
{ "x": 0.0, "y": 0.0, "z": 0.0 }
```

### 5.2 Rotation3

```json
{ "yaw": 0.0, "pitch": 0.0, "roll": 0.0 }
```

### 5.3 EntityBase

すべての配置オブジェクトは以下の考え方を共有する。

| キー | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
| `id` | string | 必須 | ステージ内で一意な識別子 |
| `name` | string | 任意 | DCC 上のオブジェクト名など |

`id` は初版から必須にする。これにより、将来的な差分更新、デバッグ表示、エラー報告、トリガー参照が安定する。

---

## 6. waypoints

`waypoints` はカメラの自動前進レールを表す順序付き配列。
順番そのものに意味があるため、配列順を経路順として扱う。

### 6.1 仕様

- 最低 2 点必要
- `id` は必須
- 回転は持たない
- 速度やイベントは持たない

### 6.2 要素構造

| キー | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
| `id` | string | 必須 | 一意識別子 |
| `position` | Vec3 | 必須 | 経路点の位置 |

### 6.3 例

```json
[
  { "id": "wp_000", "position": { "x": 0.0, "y": 0.0, "z": 0.0 } },
  { "id": "wp_001", "position": { "x": 5.0, "y": 1.0, "z": 50.0 } }
]
```

---

## 7. colliders

初版の `colliders` は **静的 Box コライダーのみ** を対象とする。
Sphere, Capsule, Mesh collider は将来拡張とし、v1 には含めない。

### 7.1 仕様

- `type` は `box` 固定
- 位置と回転はワールド値
- サイズは `halfExtents` で保持する
- 物理マテリアルは持たない

### 7.2 要素構造

| キー | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
| `id` | string | 必須 | 一意識別子 |
| `name` | string | 任意 | デバッグ表示名 |
| `type` | string | 必須 | 初版では `box` |
| `position` | Vec3 | 必須 | 中心位置 |
| `rotation` | Rotation3 | 必須 | ワールド回転 |
| `halfExtents` | Vec3 | 必須 | Box の半サイズ |
`layer` | string | 任意 | 将来のコリジョン設定用ラベル |

### 7.3 例

```json
[
  {
    "id": "col_wall_01",
    "name": "Wall_01",
    "type": "box",
    "position": { "x": 10.0, "y": 0.0, "z": 5.0 },
    "rotation": { "yaw": 0.0, "pitch": 45.0, "roll": 0.0 },
    "halfExtents": { "x": 2.0, "y": 0.5, "z": 3.0 },
    "layer": "terrain"
  }
]
```

### 7.4 初版で除外するもの

- 動的ボディ設定
- 剛体質量
- 摩擦、反発係数
- 複合コライダー

これらはエンジン側または別設定ファイルで持たせる。

---

## 8. sprites

`sprites` はビルボード表示されるエンティティの初期配置。
ここでは「何をどこに置くか」を定義し、挙動パラメータまでは持ち込まない。

### 8.1 仕様

- `type` はゲームロジック上の種別
- `position` は配置位置
- `yaw` は初期向きの参考値として保持する
- 振る舞いの詳細は別テーブルまたはコード側が解決する

### 8.2 要素構造

| キー | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
| `id` | string | 必須 | 一意識別子 |
| `name` | string | 任意 | DCC 上の名称 |
| `type` | string | 必須 | 例: `EnemyA`, `Tree`, `Gate` |
| `position` | Vec3 | 必須 | 初期配置位置 |
| `yaw` | number | 必須 | 初期 Yaw 角。度数法 |
| `params` | object | 任意 | 種別ごとの軽量追加情報 |

### 8.3 `params` の扱い

`params` は便利だが、乱用すると DCC がゲームロジック設定ツールになってしまう。
初版では以下のような軽量情報のみ許可する。

- スポーンバリエーション名
- ルート識別子
- 表示バリエーション

逆に、HP、攻撃力、AI 状態機械などのゲームバランス値は含めない。

### 8.4 例

```json
[
  {
    "id": "spr_enemy_01",
    "name": "EnemyA_01",
    "type": "EnemyA",
    "position": { "x": 10.0, "y": 2.0, "z": 50.0 },
    "yaw": 0.0,
    "params": {
      "variant": "left_flank"
    }
  }
]
```

---

## 9. triggers

`triggers` はワンショットのイベント発火ボリューム。
初版では Box Trigger のみを対象とする。

### 9.1 仕様

- `shape` は `box` 固定
- `event` がゲームロジックへ渡す意味名になる
- ボリューム形状は `position` + `rotation` + `halfExtents` で表す
- 再発火制御は初版では持たず、エンジン側で「一度だけ」として扱う

### 9.2 要素構造

| キー | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
| `id` | string | 必須 | 一意識別子 |
| `name` | string | 任意 | デバッグ名 |
| `event` | string | 必須 | 発火イベント種別 |
| `position` | Vec3 | 必須 | 中心位置 |
| `rotation` | Rotation3 | 必須 | ワールド回転 |
| `halfExtents` | Vec3 | 必須 | Box 半サイズ |
| `params` | object | 任意 | イベント追加情報 |

### 9.3 `event` の考え方

`event` はエンジン側の分岐キーとして使う。
例:

- `Checkpoint`
- `SpeedChange`
- `PlayBgm`
- `SpawnWave`

値そのものを文字列に埋め込むより、追加値は `params` に分ける。

悪い例:

```json
{ "event": "SpeedChange_120" }
```

良い例:

```json
{
  "event": "SpeedChange",
  "params": { "speed": 120 }
}
```

### 9.4 例

```json
[
  {
    "id": "trg_checkpoint_01",
    "name": "Checkpoint_01",
    "event": "Checkpoint",
    "position": { "x": 0.0, "y": 0.0, "z": 100.0 },
    "rotation": { "yaw": 0.0, "pitch": 0.0, "roll": 0.0 },
    "halfExtents": { "x": 10.0, "y": 5.0, "z": 2.0 }
  },
  {
    "id": "trg_speed_01",
    "event": "SpeedChange",
    "position": { "x": 0.0, "y": 0.0, "z": 150.0 },
    "rotation": { "yaw": 0.0, "pitch": 0.0, "roll": 0.0 },
    "halfExtents": { "x": 8.0, "y": 4.0, "z": 2.0 },
    "params": {
      "speed": 120
    }
  }
]
```

---

## 10. バリデーションルール

エクスポーターまたはインポーターは、少なくとも以下を検証する。

- `formatVersion === 1`
- `stageId` が空文字でない
- `waypoints` が 2 点以上ある
- すべての `id` が一意
- `colliders[*].type === "box"`
- `triggers[*].event` が空文字でない
- `halfExtents` の各値が正

エラーの扱いは原則として以下。

- スキーマ破壊につながるものは export fail
- 任意項目の欠落は warning 可

---

## 11. 初版の完全サンプル

```json
{
  "formatVersion": 1,
  "stageId": "stage01",
  "name": "Prototype Stage",
  "source": {
    "dcc": "Blender",
    "scene": "stage01.blend"
  },
  "waypoints": [
    { "id": "wp_000", "position": { "x": 0.0, "y": 0.0, "z": 0.0 } },
    { "id": "wp_001", "position": { "x": 0.0, "y": 0.0, "z": 50.0 } }
  ],
  "colliders": [
    {
      "id": "col_wall_01",
      "name": "Wall_01",
      "type": "box",
      "position": { "x": 12.0, "y": 0.0, "z": 48.0 },
      "rotation": { "yaw": 0.0, "pitch": 0.0, "roll": 0.0 },
      "halfExtents": { "x": 2.0, "y": 4.0, "z": 8.0 },
      "layer": "terrain"
    }
  ],
  "sprites": [
    {
      "id": "spr_enemy_01",
      "name": "EnemyA_01",
      "type": "EnemyA",
      "position": { "x": -8.0, "y": 3.0, "z": 80.0 },
      "yaw": 180.0,
      "params": {
        "variant": "alpha"
      }
    }
  ],
  "triggers": [
    {
      "id": "trg_checkpoint_01",
      "name": "Checkpoint_01",
      "event": "Checkpoint",
      "position": { "x": 0.0, "y": 0.0, "z": 120.0 },
      "rotation": { "yaw": 0.0, "pitch": 0.0, "roll": 0.0 },
      "halfExtents": { "x": 12.0, "y": 6.0, "z": 2.0 }
    }
  ]
}
```

---

## 12. 将来拡張の候補

v1 では採用しないが、将来追加しうる項目。

- `paths` や `spawnWaves` などの別カテゴリ
- `colliders` の shape 拡張
- trigger の再発火設定
- spline 補間用の補助点
- セクション分割された大規模ステージ
- アセット参照 ID の厳密化

まずは v1 を安定させ、DCC とエンジン間の契約として運用可能にすることを優先する。
