# AGENTS.md

Instructions and conventions for AI coding agents working in this repo.

For human-focused docs and usage examples, see README.md.
For error-handling expectations, see ERROR_HANDLING.md.

## What this project is

Python tool that finds which Microsoft Dataverse artifacts modify a given field:

- Business Rules (workflow category=2)
- Classic Workflows (workflow category=0)
- Power Automate Cloud Flows (workflow category=5)
- Form script Web Resources (JavaScript)

It retrieves dependencies from Dataverse, exports workflow/webresource/cloudflow content, and uses RAG (LlamaIndex + Gemini) to identify which components set values. For cloud flows, it includes advanced expression parsing (regex + AST-based with Lark) and variable tracking.

## Setup

- Python: 3.8+
- Create venv and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Required configuration

Create `.env` (see README.md for details) with:

```env
client_id=...
tenant_id=...
client_secret=...
env_url=https://<org>.crm.dynamics.com/
GOOGLE_API_KEY=...
```

## Run

```bash
# Interactive
python3 main.py

# CLI args
python3 main.py --entity account --attribute name

# Example script
python3 example_usage.py
```

Generated files (created/overwritten at runtime):

- `wf.txt` (workflow metadata)
- `webre.txt` (web resource metadata)
- `cloudflows.txt` (cloud flow metadata)
- `storage/` (vector index for workflows)
- `storage_webres/` (vector index for web resources)
- `storage_cloudflows/` (vector index for cloud flows)

## Checks

There is no automated unit test suite in this repo yet.

Minimum sanity checks after code changes:

```bash
python3 -m compileall .
```

If you can run against a real environment, also run `python3 main.py` and confirm it completes without raising.

## Conventions (keep it simple)

- Prefer straightforward functions over extra abstractions.
- Keep changes minimal and localized; avoid refactors unless required.
- Follow PEP 8 naming (snake_case) and keep methods short and focused.

## Safety / gotchas

- Secrets: never log or print `client_secret` or access tokens.
- Rate limiting: Dataverse enforces service protection limits. Respect `Retry-After` on 429s and keep using `RateLimitTracker` when making API calls.
- Token lifetime: access tokens can expire (~1 hour). Avoid long-running flows that assume tokens never refresh.
- Large payloads: business rule XAML can be large; avoid loading/storing duplicate copies unnecessarily.

## Where to change things

- Authentication / client init: `connect_to_dataverse.py`
- Dataverse reads (SDK + HTTP): `dataverse_operations.py`
- Rate limit monitoring: `rate_limit_tracker.py`
- Workflow RAG / XAML extraction: `workflow_rag.py`
- Web resource RAG / JS extraction: `webresource_rag.py`
- Cloud flow operations / retrieval: `cloudflow_operations.py`
- Cloud flow expression parsing: `expression_parser.py`
- Cloud flow RAG / field tracking: `cloudflow_rag.py`
- File I/O for exports: `file_operations.py`

### Cloud Flow Components

**expression_parser.py**
- Phase 1: Regex-based parser for common Azure Logic Apps expressions
- Phase 2: AST-based parser using Lark for complex nested expressions
- ExpressionParser: Basic regex patterns for @triggerBody(), @variables(), etc.
- AdvancedExpressionParser: AST parsing with fallback to regex
- VariableTracker: Tracks variable declarations and modifications

**cloudflow_operations.py**
- CloudFlowOperations: Retrieves active cloud flows (category=5, statecode=1)
- CloudFlowParser: Streaming JSON parser using ijson for large flows (up to 1GB)
- UpdateActionAnalyzer: Identifies Dataverse "Update a row" and "Create a new row" actions
- CloudFlowMetadataExtractor: Extracts triggers, actions, modified fields, source types, variables

**cloudflow_rag.py**
- DataverseCloudFlowRAG: RAG system for cloud flow analysis
- Parses cloudflows.txt format with field source tracking
- Methods: find_set_value_flows(), find_flows_by_trigger_type(), analyze_field_updates()
- Uses separate vector index (storage_cloudflows/) with Gemini embeddings

## Notes for agents

- If instructions conflict, user chat prompts override this file.
- If you need deeper usage details, prefer linking to README.md instead of expanding this file.
