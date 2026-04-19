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
    "（単元を指定しない）",
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
# CSS: 学習アプリ風デザイン
# ──────────────────────────────────────────────
st.markdown("""
<style>
/* ===== ページ全体の背景 ===== */
.stApp {
    background: linear-gradient(160deg, #f0f7ff 0%, #fafafa 60%, #fff8f0 100%) !important;
}


/* ===== Deploy・ハンバーガー・フッターを非表示（本番UI） ===== */
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
footer,
#MainMenu,
.stDeployButton {
    display: none !important;
}

/* ===== サイドバー ===== */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e40af 0%, #2563eb 100%) !important;
}
[data-testid="stSidebar"] * {
    color: #e0eaff !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stCaption {
    color: #bfdbfe !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.2) !important;
}
/* セレクトボックスの枠・文字を白ベースで見やすく */
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(255,255,255,0.35) !important;
    border-radius: 8px !important;
    color: white !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] svg {
    fill: white !important;
}
[data-testid="stSidebar"] button {
    background: rgba(255,255,255,0.15) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,0.25) !important;
}

/* ===== チャットメッセージ ===== */
[data-testid="stChatMessage"] {
    border-radius: 16px !important;
    margin-bottom: 8px !important;
    padding: 14px 18px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}
/* ユーザーメッセージ */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, #dbeafe, #eff6ff) !important;
    border: 1px solid #bfdbfe !important;
}
/* AIメッセージ */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
}

/* ===== フォーム内カラムの垂直中央揃え ===== */
div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
    align-items: center !important;
}
div[data-testid="stForm"] [data-testid="stHorizontalBlock"] > div {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
div[data-testid="stForm"] [data-testid="stHorizontalBlock"] > div:nth-child(2) {
    justify-content: flex-start !important;
}

/* ===== フォームコンテナ ===== */
div[data-testid="stForm"] {
    border: 2px solid #bfdbfe !important;
    border-radius: 18px !important;
    padding: 10px 14px !important;
    background: #ffffff !important;
    box-shadow: 0 4px 16px rgba(37,99,235,0.10) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
div[data-testid="stForm"]:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 4px 20px rgba(37,99,235,0.18) !important;
}

/* ===== テキストエリア ===== */
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
    color: #1e3a5f !important;
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

/* ===== ファイルアップローダー: 📎 アイコンのみ ===== */
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
div[data-testid="stFileUploader"] button {
    font-size: 0 !important;
    width: 38px !important;
    height: 38px !important;
    min-height: 0 !important;
    padding: 0 !important;
    border-radius: 10px !important;
    border: none !important;
    background: #eff6ff !important;
    color: transparent !important;
    position: relative !important;
    overflow: visible !important;
    margin: 0 auto !important;
    cursor: pointer !important;
    transition: background 0.2s !important;
}
div[data-testid="stFileUploader"] button::before {
    content: "📎";
    font-size: 1.3rem;
    color: #4b5563 !important;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    pointer-events: none;
}
div[data-testid="stFileUploader"] button:hover {
    background: #dbeafe !important;
}
div[data-testid="stFileUploaderFile"] {
    display: none !important;
}

/* ===== 送信ボタン ===== */
div[data-testid="stFormSubmitButton"] button {
    width: auto !important;
    min-width: 56px !important;
    height: 38px !important;
    min-height: 0 !important;
    padding: 0 12px !important;
    border-radius: 10px !important;
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: white !important;
    border: none !important;
    font-size: 0.9rem !important;
    font-weight: 700 !important;
    margin: 0 auto !important;
    display: block !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.35) !important;
    transition: transform 0.1s, box-shadow 0.1s !important;
    white-space: nowrap !important;
}
div[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.45) !important;
    transform: translateY(-1px) !important;
}

/* ===== 添付プレビューカード ===== */
div[data-testid="stHorizontalBlock"] > div:has(> div[data-testid="stImage"]) {
    max-width: 80px !important;
}

/* ===== 警告・情報メッセージ ===== */
[data-testid="stAlert"] {
    border-radius: 12px !important;
}

/* ===== 「Press Ctrl+Enter」英語ヒントを非表示 ===== */
[data-testid="InputInstructions"],
small:has(kbd) {
    display: none !important;
}

/* ===== モバイル対応 ===== */
@media (max-width: 768px) {
    /* フォーム内のカラムを強制的に横並びにする */
    div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 4px !important;
    }
    div[data-testid="stForm"] [data-testid="stHorizontalBlock"] > div {
        min-width: 0 !important;
        width: auto !important;
        flex-shrink: 0 !important;
    }
    /* テキスト入力列だけ伸ばす */
    div[data-testid="stForm"] [data-testid="stHorizontalBlock"] > div:nth-child(2) {
        flex: 1 1 auto !important;
        min-width: 0 !important;
    }
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
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ──────────────────────────────────────────────
# サイドバー
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 8px 0 16px;">
        <div style="font-size:3rem;">📐</div>
        <div style="font-size:1.3rem; font-weight:800; color:white; letter-spacing:0.03em;">
            数学教師くん
        </div>
        <div style="font-size:0.78rem; color:#bfdbfe; margin-top:4px;">
            いつでも気軽に質問しよう！
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.selectbox("📚 単元（任意）", UNITS, key="selected_unit")
    st.divider()
    st.caption(f"ID: `{st.session_state.user_id[:12]}...`")
    if st.button("🔄 会話をリセット", use_container_width=True):
        st.session_state.history = []
        st.session_state.pending_image = None
        st.session_state.uploader_key += 1
        st.rerun()


# ──────────────────────────────────────────────
# 会話履歴 ＋ ストリーミング用プレースホルダー
# （どちらもフォームより上に配置することで、回答がフォームの上に表示される）
# ──────────────────────────────────────────────
if not st.session_state.history:
    empty_state = st.empty()
    with empty_state:
        st.markdown("""
        <div style="text-align:center; padding:40px 20px 24px;">
            <div style="font-size:2.8rem; margin-bottom:10px;">🤔</div>
            <div style="font-size:1.05rem; font-weight:600; color:#3b82f6; margin-bottom:6px;">
                なんでも聞いてみよう！
            </div>
            <div style="font-size:0.85rem; color:#94a3b8;">
                数式・証明・解き方など、下の入力欄から送ってね。
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    empty_state = None
    for item in st.session_state.history:
        with st.chat_message("user"):
            if item.get("image_filename"):
                st.caption(f"📎 {item['image_filename']}")
            st.write(item["question"] or "（画像のみ）")
        with st.chat_message("assistant"):
            st.markdown(item["answer"])

# ストリーミング中のメッセージはここ（フォームの上）に描画する
stream_area = st.container()


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
        uploaded = st.file_uploader(
            "attach",
            type=["png", "jpg", "jpeg"],
            key=f"uploader_{st.session_state.uploader_key}",
            label_visibility="collapsed",
            help="ノートや教科書の写真を添付できます",
        )

    with col_text:
        question_input = st.text_area(
            "question",
            placeholder="質問してね（写真もOK）",
            label_visibility="collapsed",
            height=72,
            key="q_text",
        )

    with col_send:
        submitted = st.form_submit_button("送信")

st.markdown(
    "<div style='text-align:center; font-size:0.75rem; color:#94a3b8; margin-top:4px;'>"
    "📸 ノートの写真は左の <b>📎</b> から添付できます"
    "</div>",
    unsafe_allow_html=True,
)

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

    _raw_unit = st.session_state.get("selected_unit", "")
    unit = "" if _raw_unit == "（単元を指定しない）" else _raw_unit
    image_bytes    = img["bytes"]      if img else None
    media_type     = img["media_type"] if img else ""
    image_filename = img["filename"]   if img else ""

    # 空状態を消してストリーミングをフォームの上に描画する
    if empty_state is not None:
        empty_state.empty()

    with stream_area:
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
    st.session_state.uploader_key += 1
    st.rerun()

