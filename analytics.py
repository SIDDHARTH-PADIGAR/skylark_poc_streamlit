import pandas as pd
import json
from datetime import datetime
import re

# Work Order status column is "Execution Status"
WO_STATUS_MAPPINGS = {
    'completed': 'Completed',
    'not started': 'Not Started',
    'executed until current month': 'Active',
    'in progress': 'Active',
    'open': 'Active',
    'stuck': 'At Risk',
    'on hold': 'On Hold',
    'update required': 'Needs Attention'
}

# Deal Status mappings
DEAL_STATUS_MAPPINGS = {
    'open': 'Active',
    'on hold': 'On Hold',
    'dead': 'Closed Lost',
    'won': 'Closed Won'
}

# Deal Stage mappings
DEAL_STAGE_MAPPINGS = {
    'g. project won': 'Closed Won',
    'l. project lost': 'Closed Lost',
    'f. negotiations': 'Late Stage',
    'h. work order received': 'Late Stage',
    'e. proposal/commercials sent': 'Mid Stage',
    'd. feasibility': 'Mid Stage',
    'c. demo done': 'Early Stage',
    'b. sales qualified leads': 'Early Stage',
    'a. lead generated': 'Early Stage',
    'm. projects on hold': 'On Hold',
    'n. not relevant at the moment': 'Dead',
    'o. not relevant at all': 'Dead'
}

class Analytics:
    @staticmethod
    def normalize_number(value):
        if value is None or value == "":
            return 0.0
        val_str = str(value).lower().replace('$', '').replace(',', '').strip()
        try:
            multiplier = 1.0
            if 'k' in val_str:
                multiplier = 1000.0
                val_str = val_str.replace('k', '')
            elif 'm' in val_str:
                multiplier = 1000000.0
                val_str = val_str.replace('m', '')
            return float(val_str) * multiplier
        except ValueError:
            return 0.0

    @staticmethod
    def normalize_date(value, caveats):
        if value is None or value == "":
            return None
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%b %d, %Y"]
        for fmt in formats:
            try:
                return datetime.strptime(str(value).strip(), fmt)
            except ValueError:
                continue
        caveats.append(f"Unparseable date format: {value}")
        return None

    @staticmethod
    def get_column_mapping(board_metadata):
        mapping = {}
        columns = board_metadata["data"]["boards"][0]["columns"]
        for col in columns:
            title = col["title"].lower()
            col_id = col["id"]
            
            # Revenue/Value
            if any(x in title for x in ["revenue", "value", "amount"]):
                mapping["revenue"] = col_id
            # Sector
            elif any(x in title for x in ["sector", "industry"]):
                mapping["sector"] = col_id
            # Status - Priority to "Execution Status" for WO
            elif "execution status" in title:
                mapping["status"] = col_id
            elif "status" in title and "status" not in mapping:
                mapping["status"] = col_id
            # Dates - Priority to "Probable End Date" for WO
            elif "probable end date" in title:
                mapping["date"] = col_id
            elif any(x in title for x in ["date", "created", "closed"]) and "date" not in mapping:
                mapping["date"] = col_id
        return mapping

    @staticmethod
    def clean_and_parse(board_data, mapping, board_type="deals"):
        rows = []
        caveats = []
        try:
            items = board_data["data"]["boards"][0]["items_page"]["items"]
            for item in items:
                row = {"name": item["name"]}
                for val in item["column_values"]:
                    col_id = val["id"]
                    text = val["text"]
                    
                    if col_id == mapping.get("revenue"):
                        row["revenue"] = Analytics.normalize_number(text)
                    elif col_id == mapping.get("status"):
                        val_norm = str(text).lower().strip() if text else ""
                        if board_type == "deals":
                            # Check Stage first as it's more granular
                            row["status"] = DEAL_STAGE_MAPPINGS.get(val_norm, DEAL_STATUS_MAPPINGS.get(val_norm, "Other"))
                        else:
                            row["status"] = WO_STATUS_MAPPINGS.get(val_norm, "Other")
                    elif col_id == mapping.get("sector"):
                        row["sector"] = str(text).strip().title() if text else "Unknown"
                    elif col_id == mapping.get("date"):
                        row["date"] = Analytics.normalize_date(text, caveats)
                rows.append(row)
            return pd.DataFrame(rows), list(set(caveats))
        except Exception as e:
            return pd.DataFrame(), [f"Parsing error: {str(e)}"]

    @staticmethod
    def filter_by_sector(df, target_sector, caveats):
        if df.empty or not target_sector:
            return df
        target = target_sector.lower().strip()
        
        # Energy alias mapping
        search_terms = [target]
        if target == "energy":
            search_terms = ["powerline", "renewables", "energy"]
            
        mask = pd.Series([False] * len(df), index=df.index)
        for term in search_terms:
            mask |= df["sector"].str.lower().str.contains(term) | \
                    df["name"].str.lower().str.contains(term)
        
        filtered_df = df[mask]
        if filtered_df.empty:
            caveats.append(f"No results found for sector: {target_sector}")
        else:
            caveats.append(f"Applied filter: {target_sector}")
        return filtered_df

    @staticmethod
    def analyze_deals(df, caveats):
        if df.empty:
            return {"status": "No data", "total_revenue": 0, "pipeline_value": 0, "total_count": 0}
        
        total_revenue = df[df["status"] == "Closed Won"]["revenue"].sum()
        # Active includes stages between Early and Late
        pipeline_value = df[~df["status"].isin(["Closed Won", "Closed Lost", "Dead", "On Hold"])]["revenue"].sum()

        sector_summary = {}
        for sector, group in df.groupby("sector"):
            sector_summary[sector] = {"revenue": group["revenue"].sum(), "count": len(group)}

        quarterly_trends = {}
        for _, row in df.iterrows():
            dt = row.get("date")
            if dt and not pd.isna(dt):
                q = (dt.month - 1) // 3 + 1
                q_key = f"Q{q} {dt.year}"
                quarterly_trends[q_key] = quarterly_trends.get(q_key, 0) + row["revenue"]
        
        return {
            "total_revenue": total_revenue,
            "pipeline_value": pipeline_value,
            "sector_summary": sector_summary,
            "quarterly_trends": quarterly_trends,
            "total_count": len(df)
        }

    @staticmethod
    def analyze_work_orders(df):
        if df.empty:
            return {"count": 0, "status_breakdown": {}}
        status_counts = df["status"].value_counts().to_dict()
        return {"count": len(df), "status_breakdown": status_counts}

    @staticmethod
    def analyze_cross_board_risks(deals_df, wo_df):
        """
        Pivots from work orders to identify threats.
        Flags: "Not Started" or Overdue (Date < Today).
        Matches to deals by name for pipeline impact.
        """
        risks = []
        if wo_df.empty:
            return risks
            
        today = datetime.now()
        
        for _, wo in wo_df.iterrows():
            # Identification logic
            status = str(wo.get("status", "")).lower()
            is_overdue = False
            dt = wo.get("date")
            if dt and not pd.isna(dt) and dt < today and status != "completed":
                is_overdue = True
                
            is_not_started = status == "not started"
            
            if is_not_started or is_overdue:
                reason = "Not Started" if is_not_started else "Overdue"
                wo_name = str(wo["name"])
                
                # Attempt to match to deals
                match = None
                if not deals_df.empty:
                    # Clean names for matching
                    clean_wo = wo_name.lower().strip()
                    for _, deal in deals_df.iterrows():
                        clean_deal = str(deal["name"]).lower().strip()
                        if clean_deal in clean_wo or clean_wo in clean_deal:
                            match = deal
                            break
                
                if match is not None:
                    risks.append({
                        "deal_name": match["name"],
                        "pipeline_value": match.get("revenue", 0),
                        "wo_name": wo_name,
                        "issue": reason,
                        "wo_status": wo.get("status"),
                        "sector": match.get("sector", "Unknown")
                    })
                else:
                    # Fallback if no deal match
                    risks.append({
                        "deal_name": "No Match Found",
                        "pipeline_value": 0,
                        "wo_name": wo_name,
                        "issue": f"{reason} (Work Order Only)",
                        "wo_status": wo.get("status"),
                        "sector": wo.get("sector", "Unknown")
                    })
                    
        return risks

    @staticmethod
    def compare_boards(deals_metrics, wo_metrics):
        deals_count = deals_metrics.get("total_count", 0)
        wo_count = wo_metrics.get("count", 0)
        metrics = {"pipeline_value": deals_metrics.get("pipeline_value", 0), "active_work_orders": wo_count}
        if deals_count > 0 and wo_count > (deals_count * 2):
            metrics["load_status"] = "High Operational Load"
        else:
            metrics["load_status"] = "Normal"
        return metrics
