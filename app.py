import streamlit as st
import os
import json
import re
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from monday_client import MondayClient
from llm_handler import LLMHandler
from analytics import Analytics
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configure Page
st.set_page_config(page_title="Founder BI Agent", layout="wide")
load_dotenv()

# Initialize State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "monday_traces" not in st.session_state:
    st.session_state.monday_traces = []

# Header
st.title("🚀 Founder BI Agent")
st.markdown("---")

# Sidebar - Config
with st.sidebar:
    st.header("Settings")
    monday_token = os.getenv("MONDAY_API_TOKEN") or st.text_input("Monday API Token", type="password")
    deals_id = os.getenv("DEALS_BOARD_ID") or st.text_input("Deals Board ID")
    wo_id = os.getenv("WORK_ORDERS_BOARD_ID") or st.text_input("Work Orders Board ID")
    or_key = os.getenv("OPENROUTER_API_KEY") or st.text_input("OpenRouter API Key", type="password")

    if st.button("Clear History"):
        st.session_state.messages = []
        st.session_state.monday_traces = []
        st.rerun()

# Clients
if monday_token and or_key:
    monday = MondayClient(monday_token)
    llm = LLMHandler(or_key)
else:
    st.warning("Please provide all API keys in .env or sidebar to proceed.")
    st.stop()

def sanitize_text(text):
    """
    Prevents Streamlit from misinterpreting dollar signs as LaTeX.
    Replaces '$' with 'USD ' if it's near numbers, or just escapes it.
    """
    if not text:
        return text
    # Replace $100 with USD 100
    text = re.sub(r'\$(\d)', r'USD \1', text)
    # Replace any remaining $ with literal $ (escaping for markdown)
    return text.replace('$', '\\$')

# Chat Interface - Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(sanitize_text(message["content"]))
        if message["role"] == "assistant" and message.get("caveats"):
            with st.expander("⚠️ Data Quality Caveats"):
                for caveat in message["caveats"]:
                    st.write(f"- {caveat}")

# Chat Input & Processing
if prompt := st.chat_input("Ask a question about your deals or work orders..."):
    # 1. Add and display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(sanitize_text(prompt))

    # 2. Process Assistant Logic
    with st.chat_message("assistant"):
        try:
            with st.spinner("Analyzing intent..."):
                intent = llm.extract_intent(prompt, st.session_state.messages[:-1])
            
            if intent.get("clarification_needed"):
                response_text = intent["clarification_question"]
                st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            
            else:
                all_metrics = {}
                all_caveats = []
                
                with st.spinner("Fetching live data..."):
                    target_sector = intent.get("filters", {}).get("sector")
                    boards = intent.get("boards_needed", [])
                    deals_df = pd.DataFrame()
                    wo_df = pd.DataFrame()
                    
                    if "deals" in boards:
                        deals_meta = monday.get_board_columns(deals_id, board_label="Deals")
                        deals_map = Analytics.get_column_mapping(deals_meta)
                        deals_data = monday.fetch_board_items(deals_id, board_label="Deals")
                        deals_df, caveats = Analytics.clean_and_parse(deals_data, deals_map, board_type="deals")
                        if target_sector:
                            deals_df = Analytics.filter_by_sector(deals_df, target_sector, caveats)
                        all_metrics["deals"] = Analytics.analyze_deals(deals_df, caveats)
                        all_caveats.extend(caveats)
                    
                    if "work_orders" in boards:
                        wo_meta = monday.get_board_columns(wo_id, board_label="Work Orders")
                        wo_map = Analytics.get_column_mapping(wo_meta)
                        wo_data = monday.fetch_board_items(wo_id, board_label="Work Orders")
                        wo_df, caveats = Analytics.clean_and_parse(wo_data, wo_map, board_type="work_orders")
                        all_metrics["work_orders"] = Analytics.analyze_work_orders(wo_df)
                        all_caveats.extend(caveats)

                # Cross-board analysis
                if not deals_df.empty and not wo_df.empty:
                    all_metrics["cross_board_risks"] = Analytics.analyze_cross_board_risks(deals_df, wo_df)
                    all_metrics["cross_board_summary"] = Analytics.compare_boards(all_metrics["deals"], all_metrics["work_orders"])

                with st.spinner("Synthesizing insights..."):
                    summary = llm.summarize_results(prompt, all_metrics, all_caveats)
                
                sanitized_summary = sanitize_text(summary)
                st.markdown(sanitized_summary)
                
                # If specific risks exist, show them in a special alert
                if all_metrics.get("cross_board_risks"):
                    st.warning("🚨 Specific Threats Identified (Matching Deals to Work Orders):")
                    risk_df = pd.DataFrame(all_metrics["cross_board_risks"])
                    st.table(risk_df[["deal_name", "wo_name", "sector", "pipeline_value", "issue", "wo_status"]])

                if all_caveats:
                    with st.expander("⚠️ Data Quality Caveats"):
                        for caveat in list(set(all_caveats)):
                            st.write(f"- {caveat}")


                # Context-aware Dynamic Chart Dispatch
                def render_quarterly_trend(metrics):
                    trends = metrics.get("deals", {}).get("quarterly_trends", {})
                    if not trends: return None
                    def q_sort_key(q_str):
                        parts = q_str.split()
                        return (int(parts[1]), int(parts[0][1]))
                    sorted_labels = sorted(trends.keys(), key=q_sort_key)
                    sorted_values = [trends[k] for k in sorted_labels]
                    fig = px.line(x=sorted_labels, y=sorted_values, title="Quarterly Revenue Growth", labels={"x": "Quarter", "y": "Value (USD)"})
                    fig.update_layout(yaxis_tickformat="$,.2s")
                    return fig

                def render_dual_axis_sector(metrics):
                    sectors = metrics.get("deals", {}).get("sector_summary", {})
                    if not sectors: return None
                    
                    labels = list(sectors.keys())
                    values = [v["revenue"] for v in sectors.values()]
                    counts = [v["count"] for v in sectors.values()]
                    
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    # Pipeline Value Bar
                    fig.add_trace(
                        go.Bar(x=labels, y=values, name="Pipeline Value (USD)", marker_color="#1f77b4"),
                        secondary_y=False
                    )
                    
                    # Deal Count Bar (or line/scatter if preferred, but user asked for grouped bar)
                    # For a "grouped" look with dual Y, we can use an offset or just let bars overlap if needed.
                    # Actually, grouped bar on dual Y is tricky with px, so we use go.Bar
                    fig.add_trace(
                        go.Bar(x=labels, y=counts, name="Deal Count", marker_color="#ff7f0e", opacity=0.8),
                        secondary_y=True
                    )
                    
                    fig.update_layout(
                        title_text="Sector Performance: Value vs Volume",
                        xaxis_title="Sector",
                        barmode="group"
                    )
                    
                    fig.update_yaxes(title_text="Total Value (USD)", secondary_y=False, tickformat="$,.2s")
                    fig.update_yaxes(title_text="Number of Deals", secondary_y=True)
                    
                    return fig

                def render_wo_status(metrics):
                    breakdown = metrics.get("work_orders", {}).get("status_breakdown", {})
                    if not breakdown: return None
                    return px.bar(x=list(breakdown.keys()), y=list(breakdown.values()), title="Work Order Status Breakdown", labels={"x": "Status", "y": "Count"})

                CHART_DISPATCH = {
                    "quarterly_trend": render_quarterly_trend,
                    "sector_bar": render_dual_axis_sector,
                    "work_order_status": render_wo_status,
                    "stage_breakdown": render_dual_axis_sector, # Replace pie here too
                    "at_risk_deals": lambda m: None
                }

                chart_type = intent.get("chart_type")
                if chart_type in CHART_DISPATCH:
                    fig = CHART_DISPATCH[chart_type](all_metrics)
                    if fig: st.plotly_chart(fig)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": summary, 
                    "caveats": list(set(all_caveats)) if all_caveats else None
                })

        except Exception as e:
            st.error(f"Something went wrong: {str(e)}")
            st.session_state.monday_traces.append({"error": str(e), "timestamp": "N/A", "board": "Error", "status": "error"})

# Display Traces (Redesigned)
if st.session_state.monday_traces:
    st.markdown("---")
    with st.expander("🔍 API Trace Dashboard"):
        import pandas as pd
        # Create summary table
        trace_data = []
        for i, t in enumerate(st.session_state.monday_traces):
            trace_data.append({
                "#": i + 1,
                "Timestamp": t["timestamp"],
                "Board": t.get("board", "System"),
                "Status": t["status"].upper()
            })
        
        df_trace = pd.DataFrame(trace_data)
        st.dataframe(df_trace, height=200, use_container_width=True, hide_index=True)
        
        if st.checkbox("📄 Show raw trace JSON"):
            for i, t in enumerate(reversed(st.session_state.monday_traces)):
                st.markdown(f"**Call {len(st.session_state.monday_traces) - i}** ({t['timestamp']})")
                st.code(json.dumps(t, indent=2), language="json")
