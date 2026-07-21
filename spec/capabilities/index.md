# Capabilities Index

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs.

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| CSV Upload & Profiling | [csv_upload_and_profiling.md](csv_upload_and_profiling.md) | 1 |
| Data Q&A Chat | [data_qa_chat.md](data_qa_chat.md) | 1 |
| Conversation Memory | [conversation_memory.md](conversation_memory.md) | 1 |
| Audit Logging | [audit_logging.md](audit_logging.md) | 1 |

Phase 2 (multi-file join, proactive insights, export, access control) and Phase 3 (MSSQL connection, caching, sampling) capabilities are described directly in `spec/roadmap.md` under their phase blocks — dedicated capability files will be added when each phase is built.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec.
