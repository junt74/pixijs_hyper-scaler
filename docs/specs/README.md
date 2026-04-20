# specs — 仕様書・企画書

企画・技術・スケジュールに関する「文書」を置く場所です。  
**tech（実装方針）** と **gdd（ゲーム仕様）** を分けておくと、AI への指示（プロンプト）がスムーズになります。

- **tech/** … 実装方針・技術仕様。「どう実装するか」を記述する。
- **gdd/** … ゲームとしての仕様。「何をするゲームか」「ルール・判定はどうか」を記述する。
- **milestones/** … マイルストーン、リリース計画、タスク一覧

PDF や Word を置く場合は、ファイル名と概要をこの README に追記しておくと探しやすいです。

## このプロジェクトの主要ドキュメント

- `tech/Technical_Challenges_True3D_Doc1.md`
  真3D Super Scaler エンジンの中核課題と確定方針
- `tech/Framework_Selection_Doc2.md`
  サブシステムの選定方針
- `tech/Stage_JSON_Schema_Doc3.md`
  DCC から出力する `stage.json` v1 の契約
- `milestones/Near_Term_Roadmap_Doc4.md`
  エンジン実装 / Blender AddOn / 制作フローの3視点ロードマップ
