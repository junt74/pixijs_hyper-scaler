# GitHub リポジトリを Cursor の参考資料として使う

Cursor で**コーディングの参考**に GitHub のリポジトリを使うには、次の方法があります。

## 方法1: リポジトリをクローンする（推奨）

**リポジトリをワークスペース内にクローンすると、Cursor がファイルをインデックスし、検索・@ メンション・AI の参照が可能になります。**

### 手順

1. **置き場所**  
   参照用のコードは `docs/reference/libraries/` または `docs/reference/engine/` など、用途に合わせたサブフォルダに置く。

   - ライブラリ・SDK の公式リポジトリ → `docs/reference/libraries/<名前>/`
   - ゲームエンジンなど → `docs/reference/engine/<名前>/`

2. **クローン**

   ```bash
   cd docs/reference/libraries
   git clone https://github.com/Stephane-D/SGDK.git sgdk
   ```

   - 最後の `sgdk` はローカルでのフォルダ名（任意）。
   - 必要なら `--depth 1` で浅いクローンにすると軽くなります。

3. **Cursor ルールで参照先を指定（任意）**  
   「参照用にクローンしたライブラリ・エンジン・プラットフォームを質問時に参照する」ルールを `.cursor/rules/` に書いておくと、AI がそのパスを優先して参照しやすくなります（本プロジェクトでは `reference-docs.mdc` を用意しています）。

### 注意

- クローンしたリポジトリは **参考用**。プロジェクトのビルドには、パッケージマネージャや公式のインストール手順を使う。
- 大きなリポジトリは `.gitignore` で `docs/reference/libraries/*/` を除外するか、サブツリーだけ取り込む方法も検討可。

---

## 方法2: リンクだけ残す

- `docs/reference/links.md` に GitHub の URL を書いておく。
- 質問時にユーザーが「@ ウェブ」や URL を貼れば、Cursor がそのページを参照できる場合があります。
- **コードの細かい参照**（関数の使い方・サンプルコード）には向かないので、深く参照したい場合は方法1を推奨。

---

## 例: SGDK を参考にしたい場合

- **リポジトリ**: [Stephane-D/SGDK](https://github.com/Stephane-D/SGDK)（Sega Mega Drive 用 C 言語 SDK）
- **推奨配置**: `docs/reference/libraries/sgdk/` にクローン。
- **公式ドキュメント**: [SGDK Doxygen](http://stephane-d.github.io/SGDK/) は `links.md` に URL を追加しておくと便利。

クローン後は、チャットで「SGDK のスプライトの出し方」のように聞くと、`docs/reference/libraries/sgdk/` 内のコードやサンプルを参照して答えやすくなります。
