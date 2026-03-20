# ================================
# Credit Intelligence Platform
# Streamlit Dashboard — Main App
# ================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.credit_scoring import run_credit_scoring
from analysis.covenant_monitor import run_covenant_monitor, get_breach_summary
from pricing.exception_engine import run_exception_engine
from ai.credit_memo_gen import generate_credit_memo

load_dotenv()

# ================================
# Page Config
# ================================
st.set_page_config(
    page_title="Credit Intelligence Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================================
# Custom CSS
# ================================
st.markdown("""
<style>
    .main { background-color: #0a0a0f; }
    .metric-card {
        background: #111118;
        border: 1px solid #1e1e2e;
        border-radius: 4px;
        padding: 16px;
        text-align: center;
    }
    .status-red    { color: #ff4444; font-weight: bold; }
    .status-amber  { color: #ffaa00; font-weight: bold; }
    .status-green  { color: #44ff88; font-weight: bold; }
    .section-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 16px;
        border-bottom: 2px solid #1e1e2e;
        padding-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ================================
# Database Connection
# ================================
@st.cache_resource
def get_engine():
    db_url = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    return create_engine(db_url)


# ================================
# Data Loaders (cached)
# ================================
@st.cache_data(ttl=300)
def load_securities():
    engine = get_engine()
    query = text("""
        SELECT
            cusip, issuer_name, asset_class,
            instrument_type, coupon_rate,
            maturity_date, rating_sp, is_active
        FROM security_master
        ORDER BY issuer_name
    """)
    with engine.connect() as conn:
        return pd.DataFrame(conn.execute(query).fetchall())


@st.cache_data(ttl=300)
def load_pricing_exceptions():
    engine = get_engine()
    query = text("""
        SELECT
            pe.cusip,
            sm.issuer_name,
            pe.exception_date,
            pe.exception_type,
            pe.exception_desc,
            pe.deviation_pct,
            pe.is_resolved
        FROM pricing_exceptions pe
        JOIN security_master sm ON pe.cusip = sm.cusip
        ORDER BY pe.exception_date DESC
        LIMIT 100
    """)
    with engine.connect() as conn:
        return pd.DataFrame(conn.execute(query).fetchall())


@st.cache_data(ttl=300)
def load_credit_scores():
    return run_credit_scoring()


@st.cache_data(ttl=300)
def load_covenants():
    engine = get_engine()
    return get_breach_summary(engine)


# ================================
# Sidebar Navigation
# ================================
st.sidebar.image("https://via.placeholder.com/200x60?text=CIP", width=200)
st.sidebar.title("Credit Intelligence\nPlatform")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    [
        "📋 Security Master",
        "⚠️  Pricing Monitor",
        "📊 Credit Scorecard",
        "🔒 Covenant Monitor",
        "📝 Credit Memo Generator"
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Built to mirror KKR IDO workflows**\n\n"
    "Security Master · Pricing Ops · Credit Analysis · AI Memos"
)


# ================================
# PAGE 1 — Security Master
# ================================
if page == "📋 Security Master":
    st.title("📋 Security Master")
    st.markdown("All active securities with reference data and pricing status.")

    try:
        df = load_securities()

        if df.empty:
            st.warning("No securities found. Run data ingestion pipelines first.")
        else:
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                asset_filter = st.multiselect(
                    "Asset Class",
                    options=df["asset_class"].dropna().unique().tolist(),
                    default=[]
                )
            with col2:
                status_filter = st.selectbox(
                    "Status",
                    ["All", "Active Only", "Inactive Only"]
                )
            with col3:
                search = st.text_input("Search Issuer", "")

            # Apply filters
            filtered = df.copy()
            if asset_filter:
                filtered = filtered[filtered["asset_class"].isin(asset_filter)]
            if status_filter == "Active Only":
                filtered = filtered[filtered["is_active"] == True]
            elif status_filter == "Inactive Only":
                filtered = filtered[filtered["is_active"] == False]
            if search:
                filtered = filtered[
                    filtered["issuer_name"].str.contains(search, case=False, na=False)
                ]

            # Metrics row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Securities", len(df))
            m2.metric("Active", len(df[df["is_active"] == True]))
            m3.metric("Asset Classes", df["asset_class"].nunique())
            m4.metric("Filtered Results", len(filtered))

            st.dataframe(filtered, use_container_width=True, height=400)

            # Asset class breakdown chart
            st.markdown("### Asset Class Breakdown")
            ac_counts = df["asset_class"].value_counts().reset_index()
            ac_counts.columns = ["Asset Class", "Count"]
            fig = px.bar(
                ac_counts,
                x="Asset Class", y="Count",
                color="Asset Class",
                template="plotly_dark"
            )
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Database connection error: {e}")
        st.info("Make sure PostgreSQL is running and .env is configured.")


# ================================
# PAGE 2 — Pricing Monitor
# ================================
elif page == "⚠️  Pricing Monitor":
    st.title("⚠️ Pricing Exception Monitor")
    st.markdown("Daily pricing exceptions by type, severity, and issuer.")

    try:
        df = load_pricing_exceptions()

        if df.empty:
            st.warning("No pricing exceptions found. Run exception_engine.py first.")
        else:
            # Summary metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Exceptions", len(df))
            m2.metric(
                "🔴 Missing",
                len(df[df["exception_type"] == "MISSING"])
            )
            m3.metric(
                "🟡 Stale",
                len(df[df["exception_type"] == "STALE"])
            )
            m4.metric(
                "📉 Outliers",
                len(df[df["exception_type"] == "OUTLIER"])
            )

            # Exception type chart
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Exceptions by Type")
                type_counts = df["exception_type"].value_counts().reset_index()
                type_counts.columns = ["Type", "Count"]
                fig = px.pie(
                    type_counts,
                    names="Type", values="Count",
                    template="plotly_dark",
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("### Exceptions Over Time")
                if "exception_date" in df.columns:
                    daily = df.groupby("exception_date").size().reset_index()
                    daily.columns = ["Date", "Count"]
                    fig2 = px.line(
                        daily, x="Date", y="Count",
                        template="plotly_dark",
                        markers=True
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            # Exception table
            st.markdown("### Exception Detail")
            st.dataframe(
                df[["issuer_name", "exception_type",
                    "exception_date", "deviation_pct", "is_resolved"]],
                use_container_width=True,
                height=300
            )

    except Exception as e:
        st.error(f"Error loading exceptions: {e}")


# ================================
# PAGE 3 — Credit Scorecard
# ================================
elif page == "📊 Credit Scorecard":
    st.title("📊 Credit Scorecard")
    st.markdown("Fundamental credit scores ranked across all issuers.")

    try:
        df = load_credit_scores()

        if df.empty:
            st.warning("No credit scores found. Run fetch_edgar.py first.")
        else:
            # Top metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Issuers Scored", len(df))
            m2.metric(
                "Avg Credit Score",
                round(df["final_score"].mean(), 1)
            )
            m3.metric(
                "🔴 Distressed",
                len(df[df["final_score"] < 4.0])
            )
            m4.metric(
                "🟢 Inv. Grade",
                len(df[df["final_score"] >= 7.0])
            )

            # Score distribution
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Score Distribution")
                fig = px.histogram(
                    df, x="final_score",
                    nbins=10,
                    template="plotly_dark",
                    color_discrete_sequence=["#c9f31d"]
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("### Credit Rating Breakdown")
                rating_counts = df["credit_rating"].value_counts().reset_index()
                rating_counts.columns = ["Rating", "Count"]
                fig2 = px.bar(
                    rating_counts,
                    x="Rating", y="Count",
                    template="plotly_dark",
                    color="Count",
                    color_continuous_scale="RdYlGn"
                )
                st.plotly_chart(fig2, use_container_width=True)

            # Full scorecard table
            st.markdown("### Full Scorecard — Ranked Best to Worst")
            display_cols = [
                "issuer_name", "final_score", "credit_rating",
                "debt_ebitda", "interest_coverage", "trend"
            ]
            available = [c for c in display_cols if c in df.columns]
            st.dataframe(
                df[available],
                use_container_width=True,
                height=400
            )

    except Exception as e:
        st.error(f"Error loading credit scores: {e}")


# ================================
# PAGE 4 — Covenant Monitor
# ================================
elif page == "🔒 Covenant Monitor":
    st.title("🔒 Covenant Monitor")
    st.markdown("Real-time covenant compliance tracking across all issuers.")

    try:
        df = load_covenants()

        if df.empty:
            st.info("No covenant breaches or warnings detected.")
        else:
            # Summary
            red   = len(df[df["status"] == "RED"])   if "status" in df.columns else 0
            amber = len(df[df["status"] == "AMBER"]) if "status" in df.columns else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Breaches", red)
            m2.metric("🟡 Warnings", amber)
            m3.metric("Total Flagged", red + amber)

            # Color status column
            def color_status(val):
                if val == "RED":   return "color: #ff4444; font-weight: bold"
                if val == "AMBER": return "color: #ffaa00; font-weight: bold"
                if val == "GREEN": return "color: #44ff88"
                return ""

            st.markdown("### Covenant Status Table")
            st.dataframe(df, use_container_width=True, height=400)

    except Exception as e:
        st.error(f"Error loading covenant data: {e}")


# ================================
# PAGE 5 — Credit Memo Generator
# ================================
elif page == "📝 Credit Memo Generator":
    st.title("📝 AI Credit Memo Generator")
    st.markdown(
        "Generate a 1-page professional credit memo for any issuer "
        "using GPT-4o-mini and your database."
    )

    # Input
    issuer_input = st.text_input(
        "Enter Issuer Name",
        placeholder="e.g. Ford Motor"
    )

    if st.button("Generate Memo", type="primary"):
        if not issuer_input:
            st.warning("Please enter an issuer name.")
        else:
            with st.spinner(f"Generating credit memo for {issuer_input}..."):
                try:
                    memo = generate_credit_memo(issuer_input)
                    st.markdown("---")
                    st.markdown(memo)

                    # Download button
                    st.download_button(
                        label="📥 Download Memo (.md)",
                        data=memo,
                        file_name=f"{issuer_input.lower().replace(' ', '_')}_memo.md",
                        mime="text/markdown"
                    )

                except Exception as e:
                    st.error(f"Error generating memo: {e}")
                    st.info(
                        "Make sure OPENAI_API_KEY is set in .env "
                        "and the issuer exists in your database."
                    )