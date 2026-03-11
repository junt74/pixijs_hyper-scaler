# Design Philosophy: True 3D Super Scaler Engine

## 1. Core Vision
"Modern 3D Logic, Retro 2D Presentation."
- 内部ロジックは現代的な**フル3D（XYZ座標）**で管理する。
- 描画はポリゴンを使わず、**2Dスプライトの拡大縮小と並べ替え（Z-Order）**のみで行う。
- セガの『ギャラクシーフォース』のような、3D空間を自在に駆け抜ける疾走感と、ドット絵の質感を両立させる。

## 2. World Architecture (Data-Driven Design)
### Blender as a Level Editor
- **WYSIWYG:** ゲーム内の配置はすべてBlender上で行う。
- **Procedural Workflow:** `Array` や `Curve` モディファイアを活用して、トンネル、障害物の列、地形を効率的に作成する。
- **Exporter-Centric:** モディファイア適用後の最終的なワールド座標をJSON形式で抽出し、TypeScript側で「ワールドエンティティ」として再現する。

### Coordinate System
- **Right-Handed Y-Up:** - X: 左右 (Right/Left)
    - Y: 上下 (Up/Down)
    - Z: 前後 (Forward/Backward)
- Blenderの座標系（Z-Up）からゲーム用座標系への変換はエクスポート時に吸収する。



## 3. Physics & Collision (3D Rigid Body)
- **Engine:** `cannon-es` (3D Physics) を採用。
- **Decoupling:** 物理演算（ロジック）と描画（PixiJS）を完全に分離する。
- **Primitive Colliders:** - プレイヤーや敵、障害物は `Sphere` や `Box` の物理ボディを持つ。
    - 地形や壁は、Blenderから出力された座標に配置された静的（Static）な物理ボディの集合体として定義する。
- **Push-back Logic:** 衝突時の反発、壁に沿った滑り、摩擦などは物理エンジン側の計算結果をそのままスプライトの座標に同期させる。

## 4. Rendering Pipeline (The Projection Loop)
### Camera-Relative Transformation
1. **World to Local:** ワールド内の全エンティティの座標を、カメラの座標と回転（Quaternion/Matrix）に基づき「カメラ相対座標」に変換する。
2. **Culling:** カメラの後方（Local Z <= 0）にある、または描画距離外にあるエンティティを処理対象から除外する。

### 2.5D Projection Math
- カメラの焦点距離（FOV）に基づき、以下の計算式で2D座標とスケールを決定する。
    - `perspective = FOV / localZ`
    - `screenX = centerX + (localX * perspective)`
    - `screenY = centerY - (localY * perspective)`
    - `sprite.scale = perspective * baseScale`

### Z-Order Management
- 描画順を「奥から手前」へ厳密に管理する。
- `sprite.zIndex = -localZ` を活用し、PixiJSの `sortableChildren` で深度ソートを行う。



## 5. Optimization & Scalability
- **Object Pooling:** スプライトの生成・破棄はコストが高いため、カメラの範囲外に出たスプライトは「プール」に戻して再利用する。
- **Spatial Partitioning:** 膨大なワールドデータからカメラ周辺のオブジェクトのみを高速に抽出するため、空間分割（グリッド管理など）を検討する。
- **Asset Atlas:** 大量のスプライトを描画するため、テクスチャアトラスを使用してドローコールを最小化する。

## 6. Development Workflow for AI (Cursor/Claude)
1. **Physics Implementation:** まず `cannon-es` 上で3D空間を動くオブジェクトの挙動（慣性、衝突）を完成させる。
2. **Projection Layer:** 物理ボディの座標をPixiJSの画面上に投影する「カメラマネージャー」を実装する。
3. **Data Bridge:** BlenderからのJSONを読み込み、自動的に物理ボディとスプライトを生成するローダーを作成する。