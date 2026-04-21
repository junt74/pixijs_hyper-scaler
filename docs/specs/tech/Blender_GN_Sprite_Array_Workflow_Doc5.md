# Blender GN による Sprite 等間隔複製ワークフロー（Doc5）

> 対象: Blender 5 系で Geometry Nodes を用いて Sprite 配置を量産し、最終的に `stage.json` v1 へ安全にエクスポートするための制作フロー。

---

## 1. 目的

このドキュメントでは、`Sprites` の配置を Blender 上で効率化するために、
**Geometry Nodes による等間隔複製** を制作フローへ組み込む方針を定義する。

狙いは次の 3 点。

- 並木、障害物列、編隊などの繰り返し配置を高速に作る
- Blender 上では procedural に編集しつつ、最終的には安定した export を行う
- 現在の Blender exporter を大きく壊さずに運用する

---

## 2. 前提

現在の exporter は、`Sprites` Collection 配下に存在する **実オブジェクト** の Transform を読み取って `sprites[*]` を出力する。

つまり、現段階で exporter が安定して扱えるのは次のような対象である。

- `Sprites/<Type>/` 配下にある実体オブジェクト
- 各オブジェクトが持つ最終ワールド Transform
- オブジェクト名と custom property

逆に、次のものはそのままでは export 前提にしない。

- Geometry Nodes の評価結果だけに存在するインスタンス
- viewport 上では見えるが、Collection 内の個別オブジェクトとして存在しないもの
- exporter 側で special handling が必要な procedural-only データ

したがって、現時点の基本方針は次の通り。

**GN は制作補助に使うが、export 対象は最終的に実体化されたオブジェクトにする。**

---

## 3. 推奨フローの全体像

等間隔複製の推奨フローは、次の 4 段階。

1. 元になる 1 本の配置マーカーを決める
2. Geometry Nodes で等間隔配置を作る
3. Export 前に結果を実体化する
4. `Sprites/<Type>/` 配下へ整理して exporter で書き出す

このプロジェクトでは、最初から exporter に GN の評価結果を直接読ませるよりも、このワークフローのほうが安全である。

---

## 4. 基本ルール

### 4.1 `type` は Collection 名で決める

`sprites[*].type` は `Sprites` 親 Collection の子 Collection 名から決まる。

例:

- `Sprites/props/` -> `type: "props"`
- `Sprites/EnemyA/` -> `type: "EnemyA"`

したがって、GN で量産する場合も、最終的に export 対象を正しい子 Collection に置く必要がある。

### 4.2 GN で量産するのは「配置結果」

見た目メッシュを大量に増やすというより、
**Sprite の配置点を量産する** という意識で使う。

このプロジェクトで欲しいのは以下だからである。

- `position`
- `yaw`
- `type`
- 任意の軽量 `params`

つまり、最終的に重要なのは Transform であり、レンダリング用メッシュそのものではない。

### 4.3 Export 前に実体化する

現時点の運用では、GN の結果をそのまま exporter に食わせない。
以下のいずれかで実体化してから export する。

- `Realize Instances`
- 必要に応じた Bake / Convert
- 個別オブジェクト化

---

## 5. 最小ワークフロー

### 5.1 もっとも安全な作り方

最初の運用としては、次の形が一番安全。

1. `Sprites/props/` のような Collection を作る
2. その中にベースとなる marker object を 1 つ置く
3. 別オブジェクトに Geometry Nodes を設定して、等間隔の配置結果を作る
4. 結果を実体化する
5. 実体化されたオブジェクトを `Sprites/props/` 配下へ移す
6. exporter を走らせる

このフローなら、procedural 編集と安定 export を両立しやすい。

---

## 6. 直線等間隔複製の推奨構成

### 6.1 用途

以下のような配置に向く。

- 並木
- 柱の列
- ガードレール風のオブジェクト列
- 一本道に沿った装飾

### 6.2 ノード構成の考え方

代表的には、以下の構成が扱いやすい。

1. `Mesh Line`
2. `Instance on Points`
3. `Object Info` または marker object
4. `Rotate Instances` / `Translate Instances`
5. 必要なら `Realize Instances`

基本パラメータは次の通り。

- Count: 本数
- Offset / Distance: 間隔
- Start Offset: 始点のずらし
- Side Offset: 左右のずらし
- Random Seed: ばらつき用

### 6.3 並木の例

`Mesh Line` を Z 方向へ伸ばし、`Instance on Points` で marker object を配置する。

左右 1 列ずつ作る場合は次のいずれか。

- 左列と右列を別 GN object として持つ
- 1 つの GN で `Translate Instances` により左右 2 系統を作る

最初は **左右別 object** にしたほうが管理しやすい。

---

## 7. カーブ追従を使う場合

将来的にはカーブ追従も有効だが、最初は直線配置から始める。

理由:

- exporter はまだ Curve 自体を waypoint として直接扱う専用機能を持たない
- カーブ沿いの見た目と実 export 位置の検証コストが上がる
- まずは等間隔複製と export 実績を作るほうが価値が高い

カーブ追従を使う場合でも、最終的な export 方針は同じ。

- GN 上では procedural に沿わせる
- export 前には最終配置を実体化する

---

## 8. 推奨する Blender 内の役割分担

### 8.1 Source Object

元になる marker object。

用途:

- 向き確認
- 原点位置確認
- custom property の雛形

推奨:

- 単純な Empty または軽量オブジェクト
- 名前は `SRC_<Type>_...` のように分ける

### 8.2 Generator Object

GN を持つ生成用 object。

用途:

- Count / spacing / offset の調整
- procedural な複製パターン生成

推奨:

- 名前は `GEN_<Type>_...`
- export 対象そのものにしない

### 8.3 Export Objects

最終的に exporter が読む object 群。

用途:

- `Sprites/<Type>/` 配下に置く
- 実体化済みの最終配置

推奨:

- 命名は `prop_tree_000`, `prop_tree_010` のように規則化

---

## 9. Export 直前チェック

GN を使った配置では、export 前に以下を確認する。

1. `Sprites/<Type>/` 配下に実オブジェクトとして存在しているか
2. 不要な generator object が混ざっていないか
3. object 名の並びが意図通りか
4. custom property が複製結果にも必要なら維持されているか
5. 左右列や offset が Blender 上の見た目どおりか

特に注意したいのは、`Generator Object` 自体が `Sprites/<Type>/` 配下にいて誤って export されること。
generator と export 対象は分けるほうが安全である。

---

## 10. 命名規則の推奨

### 10.1 Blender object 名

最終 export 対象は、並び順と意味が分かる名前にする。

例:

- `tree_000`
- `tree_010`
- `tree_020`

左右を分けるなら:

- `tree_l_000`
- `tree_r_000`

### 10.2 Generator 名

generator は export 対象と混ざらない名前にする。

例:

- `GEN_tree_line_left`
- `GEN_tree_line_right`

### 10.3 Source 名

例:

- `SRC_tree_marker`

---

## 11. custom property の扱い

`sprites[*].params` に入れたい軽量情報がある場合、最終 export object に custom property を持たせる。

向いているもの:

- `variant`
- `route`
- `spawn_group`

避けるもの:

- HP
- 攻撃力
- AI の詳細状態

GN を通すと property 維持が分かりにくくなることがあるため、最初は **property なしでも成立する配置** から始めるのがよい。

---

## 12. 最初に試すべき題材

最初の GN 導入としておすすめなのは、次の 2 つ。

### 12.1 並木 1 列

- `props` type
- 直線
- 等間隔
- 10 本程度

### 12.2 並木 2 列

- 左右 `x = -2`, `x = 2` のような対称配置
- カメラ移動時の見え方確認に向く

このプロジェクトでは、すでに並木風の確認をしているため、ここから GN 置き換えへ移りやすい。

---

## 13. 今後の拡張候補

運用が安定したら、次を検討できる。

- exporter が GN evaluated result を直接読む
- Curve ベースの複製ガイドを正式化する
- 左右対称配置テンプレートを用意する
- GN generator 用の Blender テンプレート `.blend` を配布する

ただし、現段階ではまず

**GN で量産する -> 実体化する -> exporter で読む**

のフローを安定させることを優先する。

---

## 14. 要約

このプロジェクトにおける GN の役割は、
**Sprite の配置を procedural に設計すること** であり、
**export 契約を procedural に曖昧化すること** ではない。

したがって現時点の推奨フローは次の通り。

1. GN で等間隔複製を作る
2. 最終結果を実体化する
3. `Sprites/<Type>/` に整理する
4. exporter で `stage.json` へ出す

この流れなら、Blender 側の編集効率を上げつつ、engine 側の読み込み契約を壊さずに進められる。
