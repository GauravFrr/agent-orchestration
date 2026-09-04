# Approved Dependencies — Agent Orchestration System

Only these may be used. Any addition requires updating this file first (per AGENT.md hard rule).

## Backend (Python 3.11+)
| Package | Purpose |
|---|---|
| fastapi | API framework |
| uvicorn | ASGI server |
| pydantic (v2) | schemas / validation |
| langgraph | agent state machine / orchestration |
| langchain-core | shared LLM/tool abstractions used by LangGraph |
| google-genai | Gemini provider (reused pattern from LLM Gateway) |
| anthropic | Claude provider |
| groq | Groq provider |
| sqlalchemy | ORM (Postgres) |
| alembic | migrations |
| psycopg (or psycopg2-binary) | Postgres driver |
| redis | short-term memory + pub/sub + Celery broker |
| celery | async specialist execution + memory decay jobs |
| chromadb | long-term semantic memory |
| opentelemetry-api / -sdk | tracing |
| opentelemetry-exporter-otlp | export to local collector |
| httpx | outbound HTTP (tools, MCP client transport) |
| mcp (official Python SDK) | MCP client integration |
| tenacity | retry logic (reused pattern from LLM Gateway) |
| pytest / pytest-asyncio | testing |
| ruff | lint + format |

## Frontend (React)
| Package | Purpose |
|---|---|
| react / react-dom | UI framework |
| typescript | type safety |
| vite | build tooling |
| @tanstack/react-query | server-state fetching/caching |
| zustand (or React context) | lightweight client state |
| tailwindcss | styling |
| reactflow | plan graph + trace tree visualization |
| recharts | cost/perf strip charts |

## Infra
| Tool | Purpose |
|---|---|
| Docker / docker-compose | full-system containerization |
| PostgreSQL 15 | primary datastore (matches LLM Gateway's CI baseline) |
| Redis 7 | short-term memory, pub/sub, Celery broker |
| ChromaDB (self-hosted) | vector store |
| OpenTelemetry Collector | local trace collection, no external SaaS |

## Explicitly Deferred / Not Used
- OpenAI SDK — guide default, replaced by existing Gemini/Claude/Groq stack.
- Streamlit — replaced by React per locked decision.
- Any managed vector DB (Pinecone, Weaviate Cloud, etc.) — self-hosted ChromaDB only, consistent with self-hosted-first pattern from LLM Gateway/MemoryOS.
