"""
dashboard/app.py
AgentTrader · Streamlit 多页面主入口

启动方式：
    cd <项目根>
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

# ── 路径修正 ─────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_DASH = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_DASH))

# ── 页面配置（必须在任何 st 调用之前） ───────────────────────────────────────
_cfg_path = _ROOT / "config" / "dashboard.yaml"
_cfg = {}
if _cfg_path.exists():
    with open(_cfg_path, "r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f) or {}

st.set_page_config(
    page_title=_cfg.get("server", {}).get("title", "AgentTrader"),
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
_css_path = _DASH / "assets" / "style.css"
if _css_path.exists():
    st.markdown(
        f"<style>{_css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )

# ── 页面导入 ─────────────────────────────────────────────────────────────────
from pages.charting import render as charting_render
from pages.control import render as control_render
from pages.results import render as results_render


# ── 页面渲染函数包装 ─────────────────────────────────────────────────────────
def _page_charting():
    charting_render()

def _page_control():
    control_render()

def _page_results():
    results_render()


# ── 多页导航 ─────────────────────────────────────────────────────────────────
pg = st.navigation([
    st.Page(_page_charting, title="看盘", icon="📈"),
    st.Page(_page_control, title="控制中心", icon="🚀"),
    st.Page(_page_results, title="推荐结果", icon="📊"),
])

# ── 侧边栏品牌 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 AgentTrader")
    st.markdown("---")

pg.run()
