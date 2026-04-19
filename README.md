# 数学教師くん — 生徒質問対応 & 授業改善ログアプリ

高校数学の質問対応と、つまずきパターンの蓄積・分析を行うローカルWebアプリです。

## セットアップ

### 1. 必要なもの
- Python 3.10 以上
- Anthropic API キー

### 2. 環境変数の設定
`.env.example` をコピーして `.env` を作成し、APIキーを設定してください。

```bash
cp .env.example .env
```

`.env` を開いて編集：
```
ANTHROPIC_API_KEY=sk-ant-あなたのキー
```

### 3. ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 4. 起動

**生徒用画面**（デフォルト）
```bash
streamlit run app.py
```
ブラウザが自動で開きます（デフォルト: http://localhost:8501）

**教師用ダッシュボード**（別ポート）
```bash
streamlit run teacher_app.py --server.port 8502
```
http://localhost:8502 にアクセスし、パスコードを入力してください。

### 5. 教師パスコードの設定

`.env` ファイルに `TEACHER_PASSCODE` を設定してください（デフォルト: `math1234`）。

```
TEACHER_PASSCODE=あなたのパスコード
```

## 画面構成

| 画面 | 起動コマンド | 説明 |
|---|---|---|
| 📝 生徒用質問画面 | `streamlit run app.py` | 質問入力・画像添付・AI回答 |
| 📊 教師ダッシュボード | `streamlit run teacher_app.py --server.port 8502` | 質問ログ・分析・教師メモ（パスコード保護） |

## 画像アップロード機能

生徒は質問文に加えて、以下のような画像を添付して質問できます。

- 問題文のスキャン・写真
- 図形・グラフ
- 手書きの途中式

**対応形式**: PNG, JPG, JPEG

**保存先**: `uploads/` ディレクトリ（自動生成）

**AIの対応**:
- 図形問題では「図から読み取れる条件」と「断定できない条件」を区別
- 手書き途中式は誤りのある行を推定して説明
- 不鮮明な場合は断定せず追加情報を促す

## フォルダ構成

```
lesson_prep/
├── app.py                  # エントリーポイント
├── pages/
│   ├── student.py          # 生徒用質問画面（画像アップロード対応）
│   └── teacher.py          # 教師ダッシュボード（画像プレビュー対応）
├── core/
│   ├── ai.py               # Claude API呼び出し（画像対応ストリーミング含む）
│   ├── db.py               # SQLite CRUD（画像カラム対応）
│   └── analysis.py         # 集計・分析
├── prompts/
│   └── math_teacher.py     # システムプロンプト（カスタマイズ用）
├── data/
│   └── questions.db        # SQLite DB（自動生成）
├── uploads/                # アップロード画像保存先（自動生成）
├── .env                    # APIキー（要作成）
└── requirements.txt
```

## プロンプトのカスタマイズ

`prompts/math_teacher.py` の `CUSTOM_PROMPT_AREA` に、以前GPTsで使っていたプロンプトをそのまま貼り付けてください。

```python
CUSTOM_PROMPT_AREA = """
# ここに既存のプロンプトを貼り付ける
"""
```

## データベース

`data/questions.db`（初回起動時に自動生成）に以下のフィールドで保存されます。

| フィールド | 説明 |
|---|---|
| id | 自動採番 |
| user_id | セッションごとの仮ID |
| timestamp | 質問日時 |
| question | 質問文 |
| answer | AI回答 |
| subject_unit | 単元（AI自動分類） |
| difficulty_estimate | 難易度（AI自動分類） |
| error_type_estimate | つまずき種別（AI自動分類） |
| teacher_note | 教師メモ（手動入力） |
| has_image | 画像添付の有無（0/1） |
| image_path | 保存された画像のファイルパス |
| image_filename | 元のファイル名 |
| image_analysis_summary | 画像内容の自動要約（AIによる） |

## 将来の拡張案

- 生徒別の質問履歴追跡
- CSV/Excelエクスポート
- 分析レポートのPDF出力
- 授業プリント自動生成との連携
- プロンプトのUI編集
