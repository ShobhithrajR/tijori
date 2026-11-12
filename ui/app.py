"""Streamlit demo shell (lane 3 owns this file).

Spine state: three-pane layout, not wired to the API yet.
Lane 3 replaces the placeholders with real /v1/sanitize and /v1/process calls.
"""

from __future__ import annotations

import os

import streamlit as st

API_URL = os.getenv("TIJORI_API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Tijori — DPDP Privacy Gateway", layout="wide")
st.title("Tijori — DPDP Privacy Gateway")
st.caption("Detect the sensitive. Mask the personal. Process securely. Restore locally.")

with st.sidebar:
    st.subheader("Gateway")
    st.code(API_URL)
    doc_type = st.selectbox("Document type", ["kyc", "loan_application", "support_ticket", "insurance_claim"])
    task = st.selectbox("Task", ["summarize", "extract"])
    st.caption("Lane 3: wire these to POST /v1/process.")

sample = (
    "My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 "
    "and my PAN is ABCDE1234F."
)

left, middle, right = st.columns(3)

with left:
    st.subheader("A. Original input")
    text = st.text_area("Document", value=sample, height=320, label_visibility="collapsed")

with middle:
    st.subheader("B. Outbound sanitized payload")
    st.code("Not processed yet — call /v1/process.", language="text")
    st.warning("Leakage check: pending")

with right:
    st.subheader("C. Final response")
    st.info("Reinserted response will appear here.")

st.divider()
st.caption("Audit browser and latency panel: lane 3.")
