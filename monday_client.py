import requests
import time
import streamlit as st
from datetime import datetime

class MondayClient:
    def __init__(self, api_token):
        self.api_token = api_token
        self.api_url = "https://api.monday.com/v2"
        self.headers = {
            "Authorization": api_token,
            "Content-Type": "application/json",
            "API-Version": "2023-10"
        }
        if "monday_traces" not in st.session_state:
            st.session_state.monday_traces = []

    def _log_trace(self, query, variables, response, board="System"):
        trace = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "board": board,
            "query": query,
            "variables": variables,
            "status": "success" if "errors" not in response else "error",
            "response": response
        }
        st.session_state.monday_traces.append(trace)
        # Keep only the last 10 traces to prevent UI crash
        if len(st.session_state.monday_traces) > 10:
            st.session_state.monday_traces = st.session_state.monday_traces[-10:]

    def execute_query(self, query, variables=None, board="System"):
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            
            response = requests.post(
                self.api_url, 
                json=payload, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self._log_trace(query, variables, data, board=board)
            
            if "errors" in data:
                # Handle GraphQL errors
                error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
                raise Exception(f"Monday API Error: {error_msg}")
            
            return data
        except requests.exceptions.RequestException as e:
            self._log_trace(query, variables, {"error": str(e)})
            raise Exception(f"Connection to Monday.com failed: {str(e)}")
        except Exception as e:
            self._log_trace(query, variables, {"error": str(e)})
            raise e

    def fetch_board_items(self, board_id, board_label="Board"):
        query = """
        query ($boardId: [ID!]) {
          boards (ids: $boardId) {
            name
            columns {
              id
              title
              type
            }
            items_page (limit: 100) {
              items {
                id
                name
                column_values {
                  id
                  text
                  value
                }
              }
            }
          }
        }
        """
        variables = {"boardId": [str(board_id)]}
        return self.execute_query(query, variables, board=board_label)

    def get_board_columns(self, board_id, board_label="Board"):
        query = """
        query ($boardId: [ID!]) {
          boards (ids: $boardId) {
            columns {
              id
              title
              type
            }
          }
        }
        """
        variables = {"boardId": [str(board_id)]}
        return self.execute_query(query, variables, board=board_label)
