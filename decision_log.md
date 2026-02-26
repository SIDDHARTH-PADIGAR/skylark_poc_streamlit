# Decision Log

## Technical Architecture Choices

### 1. UI Layer: Streamlit
**Decision**: Use Streamlit for the frontend.
**Rationale**: 
- **Speed**: Allows rapid prototyping of a conversational interface within the 6-hour limit.
- **Data-First**: Native support for Plotly charts and dataframes.
- **Deployment**: Single-click deployment via Streamlit Community Cloud without managing backends.

### 2. LLM Provider: OpenRouter
**Decision**: Use OpenRouter API.
**Rationale**:
- **Flexibility**: Provides access to multiple high-quality models (GPT-4, Claude, etc.) through a single interface.
- **Reliability**: OpenAI-compatible SDK usage ensures standard integration patterns.

### 3. Logic Boundary: Deterministic Python for Math
**Decision**: Perform all metric computations in Python, not the LLM.
**Rationale**:
- **Accuracy**: LLMs are known to hallucinate numbers or fail at complex aggregations. Python (Pandas) provides 100% deterministic results.
- **Trust**: Founders need reliable data. The split between "Intent Extraction" (AI) and "Computation" (Code) preserves integrity.

### 4. Data Layer: GraphQL (Monday.com)
**Decision**: Direct GraphQL API calls on every query.
**Rationale**:
- **Freshness**: Requirement for live data means we cannot use caching or databases.
- **Precision**: GraphQL allows us to fetch only the specific columns needed, reducing payload size and increasing speed.

### 5. Transparency: API Trace
**Decision**: Visible expander at the bottom of every response.
**Rationale**:
- **Explainability**: Builds trust with the user by showing exactly how the data was fetched.
- **Debugging**: Essential for technical evaluators to see the raw GraphQL queries being sent.
