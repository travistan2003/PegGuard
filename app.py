"""PegGuard: stablecoin reserve stress tester.

Run with:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="PegGuard: Stablecoin Stress Tester", page_icon=":material/shield:",
                   layout="wide", initial_sidebar_state="expanded")

from app_pages.common import init_state, sidebar  # noqa: E402

init_state()

pages = [
    st.Page("app_pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("app_pages/stress_lab.py", title="Stress Lab", icon=":material/science:"),
    st.Page("app_pages/reserve_quality.py", title="Reserve Quality", icon=":material/fact_check:"),
    st.Page("app_pages/methodology.py", title="Methodology", icon=":material/menu_book:"),
]
nav = st.navigation(pages)
sidebar()
nav.run()
