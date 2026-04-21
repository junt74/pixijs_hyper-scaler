# tech — 実装方針・技術仕様

**「どう実装するか」** を記述する場所です。コードではなく文書で方針を残しておくと、AI への指示や実装の一貫性に役立ちます。

## このプロジェクトの主要ドキュメント

- `Technical_Challenges_True3D_Doc1.md`
  真3D Super Scaler エンジンの中核課題と確定方針
- `Framework_Selection_Doc2.md`
  入力、オーディオ、アセットロード、シーン管理などの選定方針
- `Stage_JSON_Schema_Doc3.md`
  Blender などの DCC から出力する `stage.json` の初版スキーマ
- `Blender_GN_Sprite_Array_Workflow_Doc5.md`
  Blender 5 の Geometry Nodes で Sprite を等間隔複製し、export へつなぐ制作フロー

## 記述する内容の例

- プラットフォーム制約の対応方針  
  例: 「mixi2 のレート制限（1分間10回）をどう回避するか」
- 通信・ストリームの扱い  
  例: 「gRPC ストリームの再接続ロジック」
- API の呼び出し順序やエラーハンドリング方針
- アーキテクチャやモジュール分担の説明（コード以外の文書）

謎解き・ボードゲームなど、ゲーム種別を問わず「技術的な実装の決めごと」はここにまとめます。
