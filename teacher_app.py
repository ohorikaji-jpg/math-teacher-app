import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="数学教師くん — 教師ダッシュボード",
    page_icon="📊",
    layout="wide",
)

# ──────────────────────────────────────────────
# パスコード認証
# ──────────────────────────────────────────────
def _get_passcode() -> str:
    try:
        import streamlit as _st
        v = _st.secrets.get("TEACHER_PASSCODE", "")
        if v:
            return v
    except Exception:
        pass
    return os.environ.get("TEACHER_PASSCODE", "math1234")

PASSCODE = _get_passcode()

if not st.session_state.get("teacher_authenticated"):
    st.title("📊 教師ダッシュボード")
    st.caption("このページは教師専用です。パスコードを入力してください。")

    with st.form("login_form"):
        code = st.text_input("パスコード", type="password", placeholder="パスコードを入力")
        submitted = st.form_submit_button("ログイン", use_container_width=True)

    if submitted:
        if code == PASSCODE:
            st.session_state.teacher_authenticated = True
            st.rerun()
        else:
            st.error("パスコードが違います")

    st.stop()

# ──────────────────────────────────────────────
# 認証済み → 教師ダッシュボード表示
# ──────────────────────────────────────────────
pg = st.navigation([
    st.Page("pages/teacher.py", title="ダッシュボード", icon="📊", default=True),
])
pg.run()
