#  Founder-Facing BI Agent (monday.com)

A high-signal, conversational Business Intelligence agent designed for founders to monitor their deals and operations directly from monday.com data.

##  Core Features

- **Live Data Processing**: Zero caching—every query fetches fresh data from the monday.com GraphQL API.
- **Intent-Aware Analytics**: Uses LLM extraction to determine which boards, filters, and chart types (Line, Dual-Axis Bar, Status Breakdown) are needed.
- **Dual-Axis Sector Insight**: Advanced visualization showing both Pipeline Value (USD) and Deal Volume simultaneously.
- **Cross-Board Risk Detection**: Pinpoints specific deals threatened by overdue or unstarted work orders.
- **Automatic Scaling**: Number and date normalization including shorthand support (e.g., '10m', '50k').
- **Transparent Execution**: Integrated API Trace Dashboard showing every live call made during the interaction.

##  Architecture

- **Frontend**: Streamlit (Reactive UI)
- **Analytics**: Pandas (Deterministic metric computation)
- **LLM**: Gemini 2.0 Flash (via OpenRouter)
- **Integration**: monday.com GraphQL API v2

##  Quick Start

### 1. Prerequisites
Ensure you have Python 3.9+ installed and a monday.com API token.

### 2. Environment Setup
Create a `.env` file from the example:
```bash
cp .env.example .env
```
Populate the following variables:
- `MONDAY_API_TOKEN`: Your monday.com personal API token.
- `DEALS_BOARD_ID`: The unique ID for your Deals board.
- `WORK_ORDERS_BOARD_ID`: The unique ID for your Work Orders board.
- `OPENROUTER_API_KEY`: Your OpenRouter API key.

### 3. Installation
```bash
pip install -r requirements.txt
```

### 4. Run the App
```bash
python -m streamlit run app.py
```

##  Mapping Documentation

The system is pre-configured to handle standard CRM and Project Management schemas:
- **Deals**: Maps stages (Lead -> Won) and sectors (Mining, Energy, etc.).
- **Work Orders**: Uses "Execution Status" for operational tracking and "Probable End Date" for risk analysis.
