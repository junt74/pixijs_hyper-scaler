# 直近ロードマップ（Doc4）

> 対象: PixiJS Hyper Scaler プロトタイプにおける、直近の実装・ツール・制作フローの整理。

---

## 1. このロードマップの目的

このプロジェクトは、単にエンジンを書くだけでは前進しにくい。
実際には次の3つを並行して成立させる必要がある。

- エンジンの実装
- Blender エクスポーター AddOn の実装
- 人手によるワールド／オブジェクト制作

この3つは依存関係が強い。

- エンジンは、安定した `stage.json` とサンプルデータがないと進めにくい
- エクスポーターは、エンジンが何を読むかが曖昧だと肥大化する
- 制作は、Blender 上の作法と export 成功条件が決まっていないと再現性が出ない

したがって直近の目標は、3視点が同時に回り始める **最小の縦切りライン** を作ることとする。

---

## 2. 直近の到達目標

直近では、以下を「ひとまとまりの完成形」とみなす。

1. Blender で最小ステージを作れる
2. AddOn で `stage.json` v1 をエクスポートできる
3. エンジンがその JSON を読み込み、waypoints / colliders / sprites / triggers を可視化または生成できる
4. 制作者が再現可能な手順で同じ結果を出せる

つまり、「仕様書だけある状態」から「1本の最小ステージが end-to-end で流れる状態」へ進める。

---

## 3. 進め方の原則

### 3.1 3視点を同じ優先度で扱う

エンジンだけ先に進めても、後で DCC データとの接続で止まりやすい。
逆にエクスポーターだけ先に進めても、読み込み側がないと検証できない。

そのため、毎フェーズで次の3つを必ずセットで進める。

- エンジン側の受け口
- AddOn 側の出力
- 制作側の作法

### 3.2 最初は「高度な自動化」より「再現可能性」を優先する

- まずは Box collider と単純な waypoint 列で成立させる
- Curve 等間隔サンプリングや高度な補助 UI は第二段階に回す
- 制作ルールは厳しめでもよいので、壊れにくいことを優先する

### 3.3 仕様変更は Doc3 を起点に行う

`stage.json` の契約を変える場合は、まず `Stage_JSON_Schema_Doc3.md` を更新し、その後に AddOn とエンジン実装を揃える。

---

## 4. ロードマップ全体像

直近ロードマップは 4 フェーズで進める。

| フェーズ | 主眼 | 成果物 |
| --- | --- | --- |
| Phase 1 | 契約成立 | `stage.json` v1、型、バリデータ、最小 AddOn |
| Phase 2 | 縦切り成立 | Blender -> export -> engine load の最小導通 |
| Phase 3 | 制作可能化 | 制作ルール、テンプレート scene、検証手順の明文化 |
| Phase 4 | 実運用準備 | Curve サンプリング、可視化強化、エラーメッセージ改善 |

現状は **Phase 1 完了に近く、Phase 2 着手可能** の状態とみなす。

---

## 5. Phase 1: 契約成立

### 5.1 エンジン実装

目的:

- `stage.json` v1 をコード上で扱えるようにする

実施項目:

- `StageDataV1` 型定義を整備
- ランタイムバリデータを用意
- sample JSON が validator を通る状態にする

完了条件:

- `parseStageData()` で sample JSON を読める
- エラー時に壊れたパスが追える

### 5.2 Blender エクスポーター AddOn

目的:

- v1 スキーマを壊さずに JSON を出力できる状態を作る

実施項目:

- `Waypoints`, `Colliders`, `Sprites`, `Triggers` 対応
- Scene の `stageId`, `stageName` 出力
- Export Menu と最小 UI パネルを用意

完了条件:

- Blender から `stage.json` を出力できる
- 出力結果が validator を通る

### 5.3 人手による制作

目的:

- 制作者が最低限の scene を作るためのルールを持てるようにする

実施項目:

- Collection 構造を固定
- オブジェクト命名規則の叩き台を用意
- Trigger の custom property ルールを固定

完了条件:

- 新規制作者が README を見て最小 scene を再現できる

### 5.4 状態

このフェーズは、ほぼ完了。

既にあるもの:

- Doc1, Doc2, Doc3
- TypeScript 型と validator
- 最小 Blender exporter
- sample JSON

残作業:

- 制作命名規則の細部
- Blender 側での実地検証

---

## 6. Phase 2: 縦切り成立

### 6.1 このフェーズの狙い

ここでは「実際に1本の stage を Blender から engine まで通す」ことを最優先にする。
表現の完成度より、導通確認を重視する。

### 6.2 エンジン実装

実施項目:

- `StageLoader` を追加
- `public/assets/stages/sample-stage.json` をロード
- waypoints をデバッグ表示
- colliders をデバッグ可視化
- sprites を type ごとに仮スプライト生成
- triggers をデバッグボリュームとして表示またはログ出力

完了条件:

- エンジン起動時に sample stage を読み込める
- 読み込んだ各カテゴリが画面上またはログで確認できる

補足:

この段階では、敵 AI や物理連動は最小限でよい。
まずは「JSON を読む」「位置が合う」「座標系がずれていない」を確認する。

### 6.3 Blender エクスポーター AddOn

実施項目:

- exporter の出力結果を sample-stage.json と突き合わせる
- 座標変換の向きと角度の一致を確認
- 半サイズ、回転、custom property の出力を実地検証

完了条件:

- Blender 上の配置と engine 上の配置が大きく破綻しない
- 少なくとも 1 scene で end-to-end が成功する

### 6.4 人手による制作

実施項目:

- 検証用の最小 scene を1本制作する
- waypoints だけの scene
- collider を追加した scene
- sprite / trigger を追加した scene

完了条件:

- 制作側が段階的に増築しても export と load が壊れない

### 6.5 このフェーズの最重要リスク

- Blender -> Engine の前後軸の符号ズレ
- 回転の軸解釈ズレ
- waypoint の順序と想定レールの不一致
- 制作者が collection 規約を破っても気づきにくいこと

---

## 7. Phase 3: 制作可能化

### 7.1 このフェーズの狙い

縦切りが成立したら、次は「一部の開発者しか扱えない状態」を脱して、制作作業として回る形にする。

### 7.2 エンジン実装

実施項目:

- StageLoader をモジュールとして整理
- collider / sprite / trigger のデバッグ描画切り替え
- ロード失敗時のエラーレポート改善
- type ごとの entity factory の入口を作る

完了条件:

- エンジン側でデータ不備を追跡しやすい
- ステージ読込が今後のゲーム実装の土台になる

### 7.3 Blender エクスポーター AddOn

実施項目:

- export 前バリデーションを追加
- 欠落した collection や必須 property を UI 上で報告
- ID 重複や invalid object を export 前に検出

完了条件:

- 壊れたデータが engine まで到達しにくい
- 制作者が Blender 上で問題に気づける

### 7.4 人手による制作

実施項目:

- `stage_template.blend` のようなテンプレート scene を用意
- 制作チェックリストを文書化
- 命名規則、Collection 規約、property 記入例を固定

完了条件:

- 制作者がゼロから collection を作らなくてよい
- 再現性の高い初期制作フローが成立する

---

## 8. Phase 4: 実運用準備

### 8.1 エンジン実装

実施項目:

- レール追従ロジックの本実装
- trigger 発火ロジック接続
- collider から物理ワールド生成
- sprite type ごとの実アセット接続

### 8.2 Blender エクスポーター AddOn

実施項目:

- Curve からの等間隔 waypoint サンプリング
- 複数 scene / stage 書き出し支援
- export summary の表示

### 8.3 人手による制作

実施項目:

- 実ステージ 1 本のラフ制作
- レール、障害物、敵配置、trigger 設計の試行
- 制作負荷の高い箇所を洗い出し、AddOn に還元

---

## 9. 直近 2 週間の優先順位

直近では、以下を優先順位順に進める。

1. エンジンに `StageLoader` とデバッグ表示を入れる
2. Blender exporter を実地検証して、座標系と回転のズレを確定する
3. 最小の検証用 `.blend` テンプレートを作る
4. Blender 側の export 前バリデーションを追加する
5. `sprites.type` と engine 側 entity factory の対応表を決める

---

## 10. 役割分担の考え方

### 10.1 エンジン担当が持つべき責務

- `stage.json` 契約の受け口を安定させる
- データ不備の発見を早くする
- DCC データを仮表示でもよいので可視化できるようにする

### 10.2 AddOn 担当が持つべき責務

- 制作ルールを export 結果へ確実に変換する
- 破綻したデータをできるだけ Blender 側で止める
- 制作側の手入力負荷を減らす

### 10.3 制作担当が持つべき責務

- Collection / naming / property の規約を守る
- 実データを通して、作りにくい箇所をフィードバックする
- エクスポーターやエンジンに過剰な例外対応を求める前に、作法として固定できるものを見極める

---

## 11. 直近で文書化すべき追加資料

このロードマップと合わせて、次の文書があると運用が強くなる。

- Blender 制作ガイド
  Collection 構造、命名規則、custom property 記入例
- StageLoader 設計メモ
  `stage.json` を engine オブジェクトへ変換する責務分担
- Entity type 対応表
  `sprites.type` とアセット／生成クラスの対応

---

## 12. 要約

直近で最も重要なのは、3視点を別々の TODO リストにしないこと。

まず成立させるべきなのは、次の 1 本の線である。

`Blender で作る -> AddOn で export する -> engine が load して見える`

この 1 本が成立すれば、その後の物理、演出、量産、最適化はすべて前に進めやすくなる。
直近ロードマップは、そのために必要な最小の手順をフェーズ分割したものとして扱う。
