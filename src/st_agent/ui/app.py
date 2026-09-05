"""Local Streamlit shell. Product workflows arrive in later work packages."""

from __future__ import annotations

import streamlit as st

from st_agent import __version__
from st_agent.config import load_local_env, load_settings
from st_agent.spike import credential_probe, run_strands_spike


def main() -> None:
    load_local_env()
    st.set_page_config(page_title="ST-Agent", layout="centered")
    settings = load_settings()
    st.title("ST-Agent")
    st.write(
        "This is the local runtime baseline. Character-card and lorebook "
        "workflows are not included in this package yet."
    )
    st.caption(f"Version {__version__}")
    st.write(f"Provider: `{settings.provider}`")
    st.write(f"Base URL: `{settings.base_url}`")
    st.write(f"Model ID: `{settings.model_id}`")
    st.write(
        "The development model provider is B-AI (OpenAI-compatible). "
        "Read `ST_AGENT_API_KEY` from the environment. Do not put keys in this "
        "repository or in case files. User content later sent to the model is "
        "untrusted story material."
    )
    st.subheader("Runtime spike")
    probe = credential_probe()
    st.write(
        "B-AI credentials: " + ("available" if probe.available else "missing (S-01/S-04 blocked)")
    )
    if st.button("Run S-01 spike"):
        st.json(run_strands_spike())
