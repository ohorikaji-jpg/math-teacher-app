import io
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from core.ai import classify_question, stream_answer, stream_answer_with_image, summarize_image
from core.db import init_db, save_question, update_classification

init_db()

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {"image/png", "image/jpeg"}

UNITS = [
    "",
    "数と式", "方程式・不等式", "集合と論理",
    "2次関数", "三角比", "データの分析",
    "場合の数・確率", "整数の性質", "図形の性質",
    "三角関数", "指数・対数関数",
    "微分法", "積分法",
    "数列", "ベクトル",
    "複素数・高次方程式", "式と曲線",
    "確率分布と統計的推測",
    "その他",
]

# ──────────────────────────────────────────────
# CSS: コンポーザーUI
# ──────────────────────────────────────────────
st.markdown("""
<style>
/* ===== フォームコンテナ: 1本の入力バーに見せる ===== */
div[data-testid="stForm"] {
    border: 1.5px solid #d1d5db !important;
    border-radius: 14px !important;
    padding: 8px 12px !important;
    background: #ffffff !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07) !important;
}
div[data-testid="stForm"]:focus-within {
    border-color: #9ca3af !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.12) !important;
}

/* ===== テキストエリア: 枠・背景を消してフォーム内に溶け込ませる ===== */
div[data-testid="stTextArea"] label {
    display: none !important;
}
div[data-testid="stTextArea"] textarea {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    resize: none !important;
    font-size: 0.98rem !important;
    padding: 4px 6px !important;
    color: #1f2937 !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}
div[data-testid="stTextArea"] > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

/* ===== ファイルアップローダー: 📎 アイコンのみに圧縮 ===== */
div[data-testid="stFileUploader"] label {
    display: none !important;
}
div[data-testid="stFileUploaderDropzone"] {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    min-height: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
div[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}
/* "Browse files" テキストを非表示にして 📎 アイコンに差し替え */
div[data-testid="stFileUploader"] button {
    font-size: 0 !important;
    width: 36px !important;
    height: 36px !important;
    min-height: 0 !important;
    padding: 0 !important;
    border-radius: 8px !important;
    border: none !important;
    background: transparent !important;
    color: transparent !important;
    position: relative !important;
    margin: 0 auto !important;
    cursor: pointer !important;
}
div[data-testid="stFileUploader"] button::before {
    content: "📎";
    font-size: 1.35rem;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: #6b7280;
}
div[data-testid="stFileUploader"] button:hover::before {
    color: #1f2937;
}
/* アップロード済みのStreamlit標準表示を非表示（独自プレビューを使うため） */
div[data-testid="stFileUploaderFile"] {
    display: none !important;
}

/* ===== 送信ボタン ===== */
div[data-testid="stFormSubmitButton"] button {
    width: 36px !important;
    height: 36px !important;
    min-height: 0 !important;
    padding: 0 !important;
    border-radius: 8px !important;
    background: #2563eb !important;
    color: white !important;
    border: none !important;
    font-size: 1.15rem !important;
    font-weight: bold !important;
    margin: 0 auto !important;
    display: block !important;
}
div[data-testid="stFormSubmitButton"] button:hover {
    background: #1d4ed8 !important;
}

/* ===== 添付プレビューカード ===== */
div[data-testid="stHorizontalBlock"] > div:has(> div[data-testid="stImage"]) {
    max-width: 80px !important;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# セッション初期化
# ──────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.session_state.user_id = f"student_{uuid.uuid4().hex[:8]}"
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_image" not in st.session_state:
    st.session_state.pending_image = None

# ──────────────────────────────────────────────
# サイドバー
# ──────────────────────────────────────────────
with st.sidebar:
    st.title("📐 数学教師くん")
    st.divider()
    st.selectbox("単元（任意）", UNITS, key="selected_unit")
    st.divider()
    st.caption(f"セッションID: `{st.session_state.user_id}`")
    if st.button("会話をリセット", use_container_width=True):
        st.session_state.history = []
        st.session_state.pending_image = None
        st.rerun()

# ──────────────────────────────────────────────
# タイトル
# ──────────────────────────────────────────────
st.title("📝 数学の質問をする")

# ──────────────────────────────────────────────
# 会話履歴
# ──────────────────────────────────────────────
for item in st.session_state.history:
    with st.chat_message("user"):
        if item.get("image_filename"):
            st.caption(f"📎 {item['image_filename']}")
        st.write(item["question"] or "（画像のみ）")
    with st.chat_message("assistant"):
        st.markdown(item["answer"])

# ──────────────────────────────────────────────
# 添付プレビュー（添付済みのときのみ表示）
# ──────────────────────────────────────────────
pending = st.session_state.pending_image
if pending:
    with st.container():
        col_thumb, col_name, col_clear = st.columns([1, 6, 1])
        with col_thumb:
            st.image(io.BytesIO(pending["bytes"]), width=52)
        with col_name:
            st.markdown(
                f"<div style='padding-top:14px; font-size:0.85rem; color:#374151;'>"
                f"📎 <b>{pending['filename']}</b></div>",
                unsafe_allow_html=True,
            )
        with col_clear:
            st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
            if st.button("✕", key="clear_img", help="添付を解除"):
                st.session_state.pending_image = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 入力コンポーザー
# [ 📎 ] [ テキスト入力欄（主役） ] [ ▶ ]
# ──────────────────────────────────────────────
with st.form("question_form", clear_on_submit=True):
    col_attach, col_text, col_send = st.columns([1, 9, 1])

    with col_attach:
        st.markdown("<div style='padding-top:20px'>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "attach",
            type=["png", "jpg", "jpeg"],
            key="uploader",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_text:
        question_input = st.text_area(
            "question",
            placeholder="数学の質問を入力してください（画像だけでも送れます）",
            label_visibility="collapsed",
            height=72,
            key="q_text",
        )

    with col_send:
        st.markdown("<div style='padding-top:20px'>", unsafe_allow_html=True)
        submitted = st.form_submit_button("▶")
        st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 画像選択を session_state に反映
# ──────────────────────────────────────────────
if uploaded is not None:
    mime = uploaded.type if uploaded.type in ALLOWED_TYPES else "image/jpeg"
    st.session_state.pending_image = {
        "bytes": uploaded.getvalue(),
        "filename": uploaded.name,
        "media_type": mime,
    }

# ──────────────────────────────────────────────
# 送信処理
# ──────────────────────────────────────────────
if submitted:
    question = question_input.strip()
    img = st.session_state.pending_image

    if not question and not img:
        st.warning("質問を入力するか、画像を添付してください。")
        st.stop()

    unit = st.session_state.get("selected_unit", "")
    image_bytes   = img["bytes"]     if img else None
    media_type    = img["media_type"] if img else ""
    image_filename = img["filename"]  if img else ""

    with st.chat_message("user"):
        if img:
            st.caption(f"📎 {image_filename}")
        st.write(question if question else "（画像のみ）")

    with st.chat_message("assistant"):
        try:
            if img:
                full_answer = st.write_stream(
                    stream_answer_with_image(question, image_bytes, media_type, unit)
                )
            else:
                full_answer = st.write_stream(stream_answer(question, unit))
        except EnvironmentError as e:
            st.error(str(e))
            st.stop()
        except ValueError as e:
            st.error(f"画像の処理に失敗しました: {e}")
            st.stop()

    # 画像ファイル保存
    saved_image_path = ""
    image_analysis_summary = ""
    if img:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        uid = uuid.uuid4().hex[:8]
        save_path = UPLOADS_DIR / f"{ts}_{uid}_{image_filename}"
        save_path.write_bytes(image_bytes)
        saved_image_path = str(save_path)
        try:
            image_analysis_summary = summarize_image(image_bytes, media_type)
        except Exception:
            image_analysis_summary = ""

    # DB保存
    record_id = save_question({
        "user_id":       st.session_state.user_id,
        "timestamp":     datetime.now().isoformat(),
        "question":      question,
        "answer":        full_answer,
        "subject_unit":  unit,
        "difficulty_estimate": "",
        "error_type_estimate": "",
        "teacher_note":  "",
        "has_image":     1 if img else 0,
        "image_path":    saved_image_path,
        "image_filename": image_filename,
        "image_analysis_summary": image_analysis_summary,
    })

    # 分類
    try:
        classification = classify_question(question or image_analysis_summary, full_answer)
        update_classification(record_id, classification)
    except Exception:
        pass

    st.session_state.history.append({
        "question":       question,
        "answer":         full_answer,
        "image_filename": image_filename,
    })
    st.session_state.pending_image = None
    st.rerun()
