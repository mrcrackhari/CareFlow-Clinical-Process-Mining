"""
CareFlow Clinical Pathway Dashboard — Interactive Process Mining Platform
========================================================================
Architecture: Dual-read pipeline (Primary: precomputed outputs from Member 2,
              Fallback: dynamic pandas calculations from event log).
Features: Executive KPIs, Conformance, Bottleneck SLA Alerts, Re-work Loops.
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st