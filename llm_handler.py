import os
import json
import streamlit as st
from openai import OpenAI

class LLMHandler:
    def __init__(self, api_key, model="google/gemini-2.0-flash-001"):
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

    def extract_intent(self, query, history):
        """
        Uses LLM to determine intent and which boards to query.
        """
        system_prompt = """
        You are an AI Analyst for a founder.
        Analyze the query and determine the intent, required boards, filters, and best chart type.

        JSON Output Schema:
        {
          "intent": "summary" | "comparison" | "trend" | "risk" | "sector",
          "boards_needed": ["deals", "work_orders"],
          "filters": {"sector": string | null, "stage": string | null, "date_range": string | null, "status": string | null},
          "clarification_needed": boolean,
          "clarification_question": string | null,
          "chart_type": "sector_bar" | "quarterly_trend" | "work_order_status" | "stage_breakdown" | "at_risk_deals"
        }
        """
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": f"Query: {query}"})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            intent = json.loads(response.choices[0].message.content)
            return intent
        except Exception as e:
            return {
                "intent": "summary",
                "boards_needed": ["deals"],
                "filters": {"sector": None, "stage": None, "date_range": None, "status": None},
                "clarification_needed": False,
                "clarification_question": f"Error parsing intent: {str(e)}",
                "chart_type": "sector_bar"
            }

    def summarize_results(self, user_query, python_metrics, data_quality_caveats):
        """
        Generates the Founder-ready response with business-first insights.
        """
        system_prompt = """
        You are a BI Analyst for a Founder. 
        Take raw metrics and summarize them into a high-signal response.
        
        LEAD WITH BUSINESS METRICS:
        - How much is the pipeline worth? (Total value)
        - Which sectors/stages have the most deals?
        - What needs attention from a business perspective? (e.g., stagnant deals, heavy work order load)

        STRICT RESPONSE STRUCTURE:
        1. Founder Takeaway: Exactly 1 sentence. Business-level "so what".
        2. Key Insights: Exactly 3 bullet points. Must lead with business metrics and strategic signals. 
           - CRITICAL: If specific "At Risk" deals are identified (in 'cross_board_risks'), you MUST list the exact deal names and their pipeline values here.
           - Example: "At Risk: Energy Grid deal (USD 50M) flagged due to overdue work order."
        
        STRICT FORMATTING RULE:
        - NEVER use dollar signs around numbers or mathematical notation ($).
        - Always write currency as USD prefix, example: USD 1.06B or 1.06B.
        - Never wrap values in $ symbols.
        
        DO NOT include data quality caveats here. 
        DO NOT suggest follow-up questions.
        DO NOT use itemized lists of records.
        """
        
        prompt = f"""
        User Query: {user_query}
        Computed Metrics: {json.dumps(python_metrics)}
        
        Generate the summary following the strict structure.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating summary: {str(e)}"
