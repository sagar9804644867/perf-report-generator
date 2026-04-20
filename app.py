import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import io
import base64
from datetime import datetime

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Performance Test Report Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0a0f1e; }
    .main  { background-color: #0a0f1e; }
    div[data-testid="stSidebar"] {
        background-color: #0d1526;
        border-right: 1px solid #1e3a5f;
    }
    .section-header {
        font-size: 1.1rem; font-weight: 600; color: #22d3ee;
        border-bottom: 1px solid #2d4a6e;
        padding-bottom: 8px; margin: 20px 0 15px 0;
    }
    .kpi-card {
        background: linear-gradient(135deg, #1a2035 0%, #1f2d45 100%);
        border: 1px solid #2d4a6e; border-radius: 12px;
        padding: 18px; text-align: center;
    }
    .kpi-value { font-size: 2rem; font-weight: 700; color: #22d3ee; margin: 0; }
    .kpi-label { font-size: 0.78rem; color: #94a3b8; margin: 4px 0 0 0;
                 text-transform: uppercase; letter-spacing: 1px; }
    .pass-badge { color: #22c55e; font-size: 0.8rem; }
    .fail-badge { color: #ef4444; font-size: 0.8rem; }
    h1, h2, h3 { color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Sample JTL Generator ──────────────────────────────────────
def generate_sample_jtl(n=500):
    np.random.seed(42)
    labels = ["Login", "Dashboard", "Search", "Checkout", "Profile", "Logout"]
    rows = []
    base_ts = int(datetime.now().timestamp() * 1000) - 300000
    for i in range(n):
        label = np.random.choice(labels, p=[0.2, 0.25, 0.2, 0.15, 0.15, 0.05])
        latency_map = {"Login": 800, "Dashboard": 1200, "Search": 600,
                       "Checkout": 1800, "Profile": 500, "Logout": 300}
        elapsed = max(100, int(np.random.normal(latency_map[label], latency_map[label]*0.2)))
        success = "true" if np.random.random() > 0.02 else "false"
        rc = "200" if success == "true" else np.random.choice(["500", "503", "404", "408"])
        rows.append({
            "timeStamp": base_ts + i * 600,
            "elapsed": elapsed,
            "label": label,
            "responseCode": rc,
            "responseMessage": "OK" if rc == "200" else "Error",
            "threadName": f"Thread Group 1-{(i%50)+1}",
            "dataType": "text",
            "success": success,
            "failureMessage": "" if success == "true" else "Response code was not 200",
            "bytes": np.random.randint(800, 8000),
            "sentBytes": np.random.randint(200, 600),
            "grpThreads": 50,
            "allThreads": 50,
            "URL": f"https://api.example.com/{label.lower()}",
            "Latency": max(50, elapsed - np.random.randint(10, 100)),
            "IdleTime": 0,
            "Connect": np.random.randint(5, 50),
        })
    return pd.DataFrame(rows)

# ── Parse JTL ────────────────────────────────────────────────
def parse_jtl(df):
    df["success"] = df["success"].astype(str).str.lower() == "true"
    df["elapsed"] = pd.to_numeric(df["elapsed"], errors="coerce")
    df["timeStamp"] = pd.to_numeric(df["timeStamp"], errors="coerce")
    df["datetime"] = pd.to_datetime(df["timeStamp"], unit="ms")
    df["bytes"] = pd.to_numeric(df["bytes"], errors="coerce")
    return df

# ── Compute Stats ─────────────────────────────────────────────
def compute_stats(df):
    stats = df.groupby("label").agg(
        Samples=("elapsed", "count"),
        Average=("elapsed", "mean"),
        Median=("elapsed", "median"),
        P90=("elapsed", lambda x: x.quantile(0.90)),
        P95=("elapsed", lambda x: x.quantile(0.95)),
        P99=("elapsed", lambda x: x.quantile(0.99)),
        Min=("elapsed", "min"),
        Max=("elapsed", "max"),
        Std_Dev=("elapsed", "std"),
        Error_Count=("success", lambda x: (~x).sum()),
        Throughput=("elapsed", "count"),
        Avg_Bytes=("bytes", "mean"),
    ).reset_index()
    stats["Error_%"] = (stats["Error_Count"] / stats["Samples"] * 100).round(2)
    duration_s = (df["timeStamp"].max() - df["timeStamp"].min()) / 1000
    stats["Throughput"] = (stats["Samples"] / max(duration_s, 1)).round(2)
    for col in ["Average", "Median", "P90", "P95", "P99", "Min", "Max", "Std_Dev"]:
        stats[col] = stats[col].round(1)
    stats["Avg_Bytes"] = stats["Avg_Bytes"].round(0).astype(int)
    return stats

# ── HTML Report ───────────────────────────────────────────────
def generate_html_report(df, stats, config):
    project = config.get("project", "Performance Test")
    env = config.get("env", "Production")
    tester = config.get("tester", "Sagar Chaudhary")
    threads = config.get("threads", "N/A")
    duration = config.get("duration", "N/A")
    p99_slo = config.get("p99_slo", 5000)
    error_slo = config.get("error_slo", 2.0)

    total_samples = len(df)
    overall_error = (1 - df["success"].mean()) * 100
    avg_response = df["elapsed"].mean()
    p99_overall = df["elapsed"].quantile(0.99)
    throughput = total_samples / max((df["timeStamp"].max() - df["timeStamp"].min()) / 1000, 1)
    test_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    slo_status = "PASS" if p99_overall <= p99_slo and overall_error <= error_slo else "FAIL"
    slo_color = "#22c55e" if slo_status == "PASS" else "#ef4444"

    # Build stats table rows
    table_rows = ""
    for _, row in stats.iterrows():
        err_color = "#ef4444" if row["Error_%"] > error_slo else "#22c55e"
        p99_color = "#ef4444" if row["P99"] > p99_slo else "#22d3ee"
        table_rows += f"""
        <tr>
            <td><strong>{row['label']}</strong></td>
            <td>{int(row['Samples'])}</td>
            <td>{row['Average']:.0f}</td>
            <td>{row['Median']:.0f}</td>
            <td>{row['P90']:.0f}</td>
            <td>{row['P95']:.0f}</td>
            <td style="color:{p99_color};font-weight:600">{row['P99']:.0f}</td>
            <td>{row['Min']:.0f}</td>
            <td>{row['Max']:.0f}</td>
            <td style="color:{err_color};font-weight:600">{row['Error_%']:.2f}%</td>
            <td>{row['Throughput']:.2f}/s</td>
            <td>{row['Avg_Bytes']:,}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Performance Test Report - {project}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0f1e; color: #e2e8f0; }}
  .header {{ background: linear-gradient(135deg, #0d1526 0%, #1a2035 100%);
             border-bottom: 3px solid #22d3ee; padding: 30px 40px; }}
  .header h1 {{ font-size: 2rem; color: #22d3ee; margin-bottom: 6px; }}
  .header p {{ color: #94a3b8; font-size: 0.95rem; }}
  .badge {{ display: inline-block; padding: 6px 18px; border-radius: 20px;
            font-size: 1rem; font-weight: 700; background: {slo_color}22;
            border: 2px solid {slo_color}; color: {slo_color}; margin-left: 12px; }}
  .meta {{ display: flex; gap: 30px; flex-wrap: wrap; padding: 20px 40px;
           background: #0d1526; border-bottom: 1px solid #1e3a5f; }}
  .meta-item {{ font-size: 0.85rem; color: #94a3b8; }}
  .meta-item strong {{ color: #22d3ee; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(5, 1fr);
               gap: 16px; padding: 24px 40px; }}
  .kpi {{ background: linear-gradient(135deg, #1a2035, #1f2d45);
          border: 1px solid #2d4a6e; border-radius: 12px;
          padding: 20px; text-align: center; }}
  .kpi-val {{ font-size: 2rem; font-weight: 700; color: #22d3ee; }}
  .kpi-lbl {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;
              letter-spacing: 1px; margin-top: 4px; }}
  .section {{ padding: 10px 40px 24px; }}
  .section h2 {{ font-size: 1.1rem; color: #22d3ee; border-bottom: 1px solid #2d4a6e;
                 padding-bottom: 8px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #1a2035; color: #22d3ee; padding: 10px 8px;
        text-align: left; border-bottom: 2px solid #2d4a6e; white-space: nowrap; }}
  td {{ padding: 9px 8px; border-bottom: 1px solid #1e3a5f; color: #e2e8f0; }}
  tr:hover td {{ background: #1a2035; }}
  .slo-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .slo-item {{ background: #1a2035; border: 1px solid #2d4a6e;
               border-radius: 8px; padding: 14px; }}
  .slo-item .label {{ font-size: 0.82rem; color: #94a3b8; margin-bottom: 4px; }}
  .slo-item .val {{ font-size: 1.1rem; font-weight: 600; }}
  .footer {{ text-align: center; padding: 20px; color: #475569; font-size: 0.8rem;
             border-top: 1px solid #1e3a5f; margin-top: 20px; }}
  @media print {{ body {{ background: white; color: black; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 {project} — Performance Test Report
    <span class="badge">{'✅ PASS' if slo_status == 'PASS' else '❌ FAIL'}</span>
  </h1>
  <p>Generated by Performance Test Report Generator | Built by Sagar Chaudhary</p>
</div>

<div class="meta">
  <div class="meta-item"><strong>Environment:</strong> {env}</div>
  <div class="meta-item"><strong>Test Date:</strong> {test_date}</div>
  <div class="meta-item"><strong>Tester:</strong> {tester}</div>
  <div class="meta-item"><strong>Virtual Users:</strong> {threads}</div>
  <div class="meta-item"><strong>Duration:</strong> {duration}s</div>
  <div class="meta-item"><strong>P99 SLO:</strong> {p99_slo}ms</div>
  <div class="meta-item"><strong>Error Rate SLO:</strong> {error_slo}%</div>
</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-val">{total_samples:,}</div><div class="kpi-lbl">Total Samples</div></div>
  <div class="kpi"><div class="kpi-val">{avg_response:.0f}ms</div><div class="kpi-lbl">Avg Response</div></div>
  <div class="kpi"><div class="kpi-val" style="color:{'#ef4444' if p99_overall > p99_slo else '#22d3ee'}">{p99_overall:.0f}ms</div><div class="kpi-lbl">P99 Latency</div></div>
  <div class="kpi"><div class="kpi-val" style="color:{'#ef4444' if overall_error > error_slo else '#22c55e'}">{overall_error:.2f}%</div><div class="kpi-lbl">Error Rate</div></div>
  <div class="kpi"><div class="kpi-val">{throughput:.1f}/s</div><div class="kpi-lbl">Throughput</div></div>
</div>

<div class="section">
  <h2>📋 Results by Transaction</h2>
  <table>
    <thead>
      <tr>
        <th>Label</th><th>Samples</th><th>Avg (ms)</th><th>Median</th>
        <th>P90</th><th>P95</th><th>P99</th><th>Min</th><th>Max</th>
        <th>Error %</th><th>Throughput</th><th>Avg Bytes</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>🎯 SLO Compliance</h2>
  <div class="slo-grid">
    <div class="slo-item">
      <div class="label">P99 Latency vs SLO ({p99_slo}ms)</div>
      <div class="val" style="color:{'#22c55e' if p99_overall <= p99_slo else '#ef4444'}">
        {p99_overall:.0f}ms — {'✅ PASS' if p99_overall <= p99_slo else '❌ FAIL'}
      </div>
    </div>
    <div class="slo-item">
      <div class="label">Error Rate vs SLO ({error_slo}%)</div>
      <div class="val" style="color:{'#22c55e' if overall_error <= error_slo else '#ef4444'}">
        {overall_error:.2f}% — {'✅ PASS' if overall_error <= error_slo else '❌ FAIL'}
      </div>
    </div>
    <div class="slo-item">
      <div class="label">Overall SLO Status</div>
      <div class="val" style="color:{slo_color}">{slo_status}</div>
    </div>
    <div class="slo-item">
      <div class="label">Total Errors</div>
      <div class="val" style="color:#ef4444">{int((~df['success']).sum())} / {total_samples}</div>
    </div>
  </div>
</div>

<div class="footer">
  Performance Test Report Generator | Built by <strong>Sagar Chaudhary</strong> |
  Performance Engineering Lead @ PwC India |
  <a href="https://sagar-portfolio-new.vercel.app" style="color:#22d3ee">Portfolio</a> |
  <a href="https://linkedin.com/in/sagar-chaudhary-024254130" style="color:#22d3ee">LinkedIn</a>
</div>
</body>
</html>"""
    return html

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Report Generator")
    st.markdown("*by Sagar Chaudhary*")
    st.markdown("---")
    st.markdown("### 📁 Supported Formats")
    st.markdown("- JMeter JTL (CSV)")
    st.markdown("- JMeter JTL (XML) *coming soon*")
    st.markdown("- K6 CSV *coming soon*")
    st.markdown("---")
    st.markdown("### 🔗 Links")
    st.markdown("[Portfolio](https://sagar-portfolio-new.vercel.app) | [LinkedIn](https://linkedin.com/in/sagar-chaudhary-024254130)")

# ── Main ──────────────────────────────────────────────────────
st.markdown("# 📊 Performance Test Report Generator")
st.markdown("Upload your **JMeter JTL file** and generate a professional HTML report instantly.")
st.markdown("---")

# ── Config ────────────────────────────────────────────────────
st.markdown('<p class="section-header">⚙️ Report Configuration</p>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    project_name = st.text_input("Project Name", value="API Performance Test")
    environment  = st.text_input("Environment", value="Production")
with col2:
    tester_name  = st.text_input("Tester Name", value="Sagar Chaudhary")
    virtual_users = st.number_input("Virtual Users", value=50, min_value=1)
with col3:
    test_duration = st.number_input("Test Duration (s)", value=300, min_value=1)
    p99_slo = st.number_input("P99 Latency SLO (ms)", value=5000, step=500)
    error_slo = st.number_input("Error Rate SLO (%)", value=2.0, step=0.5)

# ── Upload ────────────────────────────────────────────────────
st.markdown('<p class="section-header">📁 Upload JTL File</p>', unsafe_allow_html=True)
col_u1, col_u2 = st.columns([2, 1])
with col_u1:
    uploaded = st.file_uploader("Upload JMeter JTL (CSV format)", type=["jtl", "csv"])
with col_u2:
    use_sample = st.checkbox("Use sample data (demo)", value=True)
    st.caption("Simulates 500 requests across 6 transactions")

# ── Load Data ─────────────────────────────────────────────────
df = None
if uploaded:
    try:
        df = pd.read_csv(uploaded)
        df = parse_jtl(df)
        st.success(f"✅ Loaded {len(df):,} records from JTL file")
        use_sample = False
    except Exception as e:
        st.error(f"❌ Error parsing file: {e}")

if use_sample and df is None:
    df = generate_sample_jtl(500)
    df = parse_jtl(df)
    st.info("📊 Using sample data — upload your own JTL file to generate a real report")

# ── Analysis ──────────────────────────────────────────────────
if df is not None:
    stats = compute_stats(df)
    config = {
        "project": project_name, "env": environment, "tester": tester_name,
        "threads": virtual_users, "duration": test_duration,
        "p99_slo": p99_slo, "error_slo": error_slo
    }

    # KPIs
    st.markdown('<p class="section-header">📈 Key Performance Indicators</p>', unsafe_allow_html=True)
    total = len(df)
    err_pct = (1 - df["success"].mean()) * 100
    p99 = df["elapsed"].quantile(0.99)
    avg_r = df["elapsed"].mean()
    tput = total / max((df["timeStamp"].max() - df["timeStamp"].min()) / 1000, 1)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="kpi-card"><p class="kpi-value">{total:,}</p><p class="kpi-label">Total Samples</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-card"><p class="kpi-value">{avg_r:.0f}ms</p><p class="kpi-label">Avg Response</p></div>', unsafe_allow_html=True)
    with c3:
        col = "#ef4444" if p99 > p99_slo else "#22d3ee"
        st.markdown(f'<div class="kpi-card"><p class="kpi-value" style="color:{col}">{p99:.0f}ms</p><p class="kpi-label">P99 Latency</p><p class="{"fail-badge" if p99>p99_slo else "pass-badge"}">{"❌ SLO Breach" if p99>p99_slo else "✅ Within SLO"}</p></div>', unsafe_allow_html=True)
    with c4:
        col = "#ef4444" if err_pct > error_slo else "#22c55e"
        st.markdown(f'<div class="kpi-card"><p class="kpi-value" style="color:{col}">{err_pct:.2f}%</p><p class="kpi-label">Error Rate</p><p class="{"fail-badge" if err_pct>error_slo else "pass-badge"}">{"❌ SLO Breach" if err_pct>error_slo else "✅ Within SLO"}</p></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="kpi-card"><p class="kpi-value">{tput:.1f}/s</p><p class="kpi-label">Throughput</p></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<p class="section-header">⏱️ Response Time Percentiles</p>', unsafe_allow_html=True)
        fig1 = go.Figure()
        colors = px.colors.qualitative.Set2
        for i, pct in enumerate(["P90", "P95", "P99"]):
            fig1.add_trace(go.Bar(
                name=pct, x=stats["label"], y=stats[pct],
                marker_color=["#22d3ee", "#f59e0b", "#ef4444"][i], opacity=0.85
            ))
        fig1.add_hline(y=p99_slo, line_dash="dash", line_color="#ef4444",
                       annotation_text=f"P99 SLO ({p99_slo}ms)")
        fig1.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2035", plot_bgcolor="#1a2035",
            height=350, margin=dict(l=10, r=10, t=10, b=60),
            barmode="group", yaxis_title="Response Time (ms)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            xaxis_tickangle=-20
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.markdown('<p class="section-header">❌ Error Rate by Transaction</p>', unsafe_allow_html=True)
        colors_err = ["#ef4444" if e > error_slo else "#22c55e" for e in stats["Error_%"]]
        fig2 = go.Figure(go.Bar(
            x=stats["label"], y=stats["Error_%"],
            marker_color=colors_err, opacity=0.85
        ))
        fig2.add_hline(y=error_slo, line_dash="dash", line_color="#f59e0b",
                       annotation_text=f"Error SLO ({error_slo}%)")
        fig2.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2035", plot_bgcolor="#1a2035",
            height=350, margin=dict(l=10, r=10, t=10, b=60),
            yaxis_title="Error Rate (%)", xaxis_tickangle=-20
        )
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown('<p class="section-header">📈 Response Time Over Time</p>', unsafe_allow_html=True)
        df_sorted = df.sort_values("datetime")
        df_rolled = df_sorted.set_index("datetime")["elapsed"].rolling("30s").mean().reset_index()
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df_rolled["datetime"], y=df_rolled["elapsed"],
                                  mode="lines", name="Avg Response",
                                  line=dict(color="#22d3ee", width=2)))
        fig3.add_hline(y=p99_slo, line_dash="dash", line_color="#ef4444",
                       annotation_text="P99 SLO")
        fig3.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2035", plot_bgcolor="#1a2035",
            height=350, margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Response Time (ms)", xaxis_title="Time"
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown('<p class="section-header">🔢 Throughput by Transaction</p>', unsafe_allow_html=True)
        fig4 = px.bar(stats, x="label", y="Throughput",
                      color="Throughput", color_continuous_scale="Blues",
                      labels={"Throughput": "Requests/sec", "label": "Transaction"})
        fig4.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2035", plot_bgcolor="#1a2035",
            height=350, margin=dict(l=10, r=10, t=10, b=60),
            coloraxis_showscale=False, xaxis_tickangle=-20
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Stats Table
    st.markdown('<p class="section-header">📋 Summary Statistics Table</p>', unsafe_allow_html=True)
    display_stats = stats[["label", "Samples", "Average", "Median", "P90",
                            "P95", "P99", "Min", "Max", "Error_%", "Throughput", "Avg_Bytes"]].copy()
    display_stats.columns = ["Transaction", "Samples", "Avg(ms)", "Median",
                              "P90", "P95", "P99", "Min", "Max", "Error%", "Throughput/s", "Avg Bytes"]
    st.dataframe(display_stats.set_index("Transaction"), use_container_width=True)

    # Error breakdown
    if (~df["success"]).sum() > 0:
        st.markdown('<p class="section-header">🚨 Error Breakdown</p>', unsafe_allow_html=True)
        err_df = df[~df["success"]].groupby(["label", "responseCode"]).size().reset_index(name="Count")
        st.dataframe(err_df, use_container_width=True)

    # Generate & Download
    st.markdown("---")
    st.markdown('<p class="section-header">📥 Generate Report</p>', unsafe_allow_html=True)
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        if st.button("🚀 Generate HTML Report", type="primary", use_container_width=True):
            html = generate_html_report(df, stats, config)
            fname = f"{project_name.replace(' ','_')}_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            st.download_button(
                "📥 Download HTML Report", data=html,
                file_name=fname, mime="text/html", use_container_width=True
            )
            st.success("✅ Report generated! Click above to download.")

    with col_g2:
        csv_data = stats.to_csv(index=False)
        st.download_button(
            "📥 Download Stats CSV", data=csv_data,
            file_name=f"{project_name.replace(' ','_')}_Stats.csv",
            mime="text/csv", use_container_width=True
        )

st.markdown("---")
st.caption("Built by **Sagar Chaudhary** | Performance Engineering Lead @ PwC India | [Portfolio](https://sagar-portfolio-new.vercel.app) | [LinkedIn](https://linkedin.com/in/sagar-chaudhary-024254130)")
