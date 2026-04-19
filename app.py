import streamlit as st

st.set_page_config(
    page_title="数学教師くん",
    page_icon="📐",
    layout="wide",
)

pg = st.navigation([
    st.Page("pages/student.py", title="質問する", icon="📝", default=True),
])
pg.run()
