"""Local Streamlit shell. Product workflows arrive in later work packages."""

from __future__ import annotations

import streamlit as st

from st_agent import __version__
from st_agent.config import load_settings
from st_agent.spike import credential_probe, run_strands_spike


def main() -> None:
    st.set_page_config(page_title="ST-Agent", layout="centered")
    settings = load_settings()
    st.title("ST-Agent")
    st.write(
        "This is the local runtime baseline. Character-card and lorebook "
        "workflows are not included in this package yet."
    )
    st.caption(f"Version {__version__}")
    if settings.aws_region:
        st.write(f"AWS region: `{settings.aws_region}`")
    else:
        st.write(
            "AWS region is not set. Configure `AWS_REGION` or `AWS_DEFAULT_REGION`."
        )
    st.write(f"Model ID: `{settings.model_id}`")
    st.write(
        "Credentials use the standard AWS provider chain. "
        "Do not put access keys in this repository or in case files. "
        "User content that later work packages send to Bedrock is untrusted story material."
    )
    st.subheader("Runtime spike")
    probe = credential_probe()
    st.write(
        "Bedrock credentials: "
        + ("available" if probe.available else "missing (S-01/S-04 blocked)")
    )
    if st.button("Run S-01 spike"):
        st.json(run_strands_spike())
