# Backend Schema — Agent Orchestration System

## PostgreSQL Tables

### tasks
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| request_text | TEXT | original natural-language request |
| status | ENUM | intake, planning, executing, reviewing, escalated, synthesizing, done, failed |
| plan | JSONB | current Plan object |
| confidence | FLOAT | supervisor's plan confidence |
| created_at / updated_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ NULL | |
| total_cost_usd | NUMERIC(10,6) | rolled up from spans |

### subtasks
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| task_id | UUID FK → tasks | |
| specialist | TEXT | research / data_analysis / writing / code_exec |
| input | JSONB | |
| depends_on | UUID[] | subtask ids |
| status | ENUM | pending, running, review_pending, approved, rejected, retried, done, failed |
| retry_count | INT DEFAULT 0 | |
| output | JSONB NULL | |
| reviewer_verdict | ENUM NULL | approve, reject, escalate |
| reviewer_feedback | TEXT NULL | |

### tool_invocations
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| subtask_id | UUID FK → subtasks | |
| tool_name | TEXT | |
| tool_kind | ENUM | custom, mcp |
| input | JSONB | |
| output | JSONB | |
| latency_ms | INT | |
| success | BOOLEAN | |
| error | TEXT NULL | |
| cost_usd | NUMERIC(10,6) NULL | |
| created_at | TIMESTAMPTZ | |

### review_requests
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| task_id | UUID FK → tasks | |
| subtask_id | UUID FK NULL | null if plan-level review |
| trigger_reason | TEXT | e.g. "low_confidence", "sensitive_action", "repeated_failure" |
| approval_level | ENUM | notify, approve_action, approve_plan, take_over |
| context_snapshot | JSONB | full context at pause time |
| status | ENUM | pending, approved, rejected, modified, taken_over |
| decision_payload | JSONB NULL | human's modification / takeover output |
| created_at / decided_at | TIMESTAMPTZ | |

### memories
Metadata mirror of ChromaDB entries (vectors live in Chroma; Postgres holds the queryable/manageable metadata).
| column | type | notes |
|---|---|---|
| id | UUID PK | matches Chroma document id |
| source_task_id | UUID FK → tasks | |
| memory_type | ENUM | plan, fact, preference |
| summary | TEXT | human-readable summary stored alongside embedding |
| importance_score | FLOAT | recency + retrieval_count + outcome |
| retrieval_count | INT DEFAULT 0 | |
| last_retrieved_at | TIMESTAMPTZ NULL | |
| created_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ NULL | soft delete before hard purge job |

### trace_spans
| column | type | notes |
|---|---|---|
| id | UUID PK | otel span id |
| task_id | UUID FK → tasks | |
| parent_span_id | UUID NULL | |
| span_type | ENUM | plan, dispatch, tool_call, review, memory_retrieval, escalation, synthesize |
| actor | TEXT | supervisor / specialist name / reviewer |
| started_at / ended_at | TIMESTAMPTZ | |
| latency_ms | INT | |
| cost_usd | NUMERIC(10,6) NULL | |
| tokens_in / tokens_out | INT NULL | |
| payload | JSONB | prompt/response or tool io, for expand-in-UI |

### checkpoints
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| task_id | UUID FK → tasks | |
| node_name | TEXT | LangGraph node at time of checkpoint |
| state_snapshot | JSONB | full LangGraph state |
| created_at | TIMESTAMPTZ | |

### replays
| column | type | notes |
|---|---|---|
| id | UUID PK | new run id |
| original_task_id | UUID FK → tasks | |
| from_checkpoint_id | UUID FK → checkpoints | |
| input_override | JSONB NULL | |
| resulting_task_id | UUID FK → tasks | the new task row this replay produced |
| created_at | TIMESTAMPTZ | |

## ChromaDB Collections
- `plans` — embedding of `{request_text}`, metadata `{task_id, final_plan_summary, outcome}`
- `facts` — embedding of discovered domain facts, metadata `{task_id, fact_text, specialist}`
- `preferences` — embedding of inferred user preferences, metadata `{task_id, preference_text}`

## Redis Keyspace
- `task:{id}:state` — short-term working memory (plan, completed outputs, error log), TTL 24h post-completion
- `review:{id}:pending` — pub/sub channel for human review notifications
- `celery` — standard Celery broker/result keys
- `circuit:{provider}` — reused pattern from LLM Gateway if provider-level circuit breaking is added to agent LLM calls
