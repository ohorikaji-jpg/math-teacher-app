import base64
import json
import os
from typing import Generator

import anthropic
from dotenv import load_dotenv

from core.image import compress_for_api
from prompts.math_teacher import CLASSIFICATION_PROMPT, build_system_prompt

load_dotenv()

ANSWER_MODEL = "claude-sonnet-4-6"
CLASSIFY_MODEL = "claude-haiku-4-5-20251001"


def _get_api_key() -> str:
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _client() -> anthropic.Anthropic:
    api_key = _get_api_key()
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")
    return anthropic.Anthropic(api_key=api_key)


def stream_answer(question: str, unit: str = "") -> Generator[str, None, None]:
    """Claude APIにストリーミングで回答を取得するジェネレータ（st.write_stream対応）"""
    with _client().messages.stream(
        model=ANSWER_MODEL,
        max_tokens=2048,
        system=build_system_prompt(unit),
        messages=[{"role": "user", "content": question}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_answer_with_image(
    question: str,
    image_bytes: bytes,
    media_type: str,
    unit: str = "",
) -> Generator[str, None, None]:
    """画像付きでストリーミング回答を取得するジェネレータ（st.write_stream対応）"""
    # API送信前に圧縮（5MB制限対策）。失敗時は ValueError を送出
    image_bytes, media_type = compress_for_api(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        },
        {
            "type": "text",
            "text": question if question.strip() else "（画像を確認して、内容を説明してください）",
        },
    ]
    with _client().messages.stream(
        model=ANSWER_MODEL,
        max_tokens=2048,
        system=build_system_prompt(unit, with_image=True),
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def summarize_image(image_bytes: bytes, media_type: str) -> str:
    """画像から読み取れた内容の簡易要約を返す（ログ保存用）"""
    # API送信前に圧縮。失敗しても要約は任意処理なので空文字で握りつぶす
    try:
        image_bytes, media_type = compress_for_api(image_bytes)
    except ValueError:
        return ""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = _client().messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {
                        "type": "text",
                        "text": "この画像に含まれる数学的内容を50字以内で簡潔に要約してください（例：「二次方程式の手書き途中式」「三角形の図形問題」）。",
                    },
                ],
            }
        ],
    )
    try:
        return response.content[0].text.strip()
    except (IndexError, AttributeError):
        return ""


def classify_question(question: str, answer: str) -> dict:
    """質問と回答を分析して単元・難易度・つまずき種別を返す"""
    prompt = CLASSIFICATION_PROMPT.format(
        question=question,
        answer_summary=answer[:500],
    )
    response = _client().messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        text = response.content[0].text.strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError, KeyError):
        return {
            "subject_unit": "",
            "difficulty_estimate": "",
            "error_type_estimate": "その他",
        }


def generate_followup_suggestions(
    unit_ranking: str,
    error_ranking: str,
    recent_trend: str,
    image_ratio: float,
) -> list[str]:
    """蓄積データを元に次回授業のフォローポイントを3つ生成する"""
    prompt = f"""\
以下は高校数学の授業で生徒から寄せられた質問ログの集計データです。

【単元別質問数（上位）】
{unit_ranking}

【つまずき種別（上位）】
{error_ranking}

【直近7日間のトレンド】
{recent_trend}

【画像付き質問の割合】
全質問のうち {image_ratio}% が図・グラフ・手書き式の画像を添付した質問でした。

このデータをもとに、教師が次の授業でとるべき具体的なフォローアクションを3つ提案してください。
- 各ポイントは1〜2文の日本語で
- 「〜する」「〜を確認する」など動詞で終わる具体的なアクションにする
- データの根拠（どの単元・つまずきが多いか）に基づいて説明する
- JSON配列のみを返す（コードブロック不要）: ["ポイント1", "ポイント2", "ポイント3"]
"""
    response = _client().messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        text = response.content[0].text.strip()
        suggestions = json.loads(text)
        if isinstance(suggestions, list):
            return suggestions[:3]
        return []
    except (json.JSONDecodeError, IndexError):
        return []
