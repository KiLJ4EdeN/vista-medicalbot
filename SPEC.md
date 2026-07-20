# Mudawi Medical Assistant

## Overview

Multilingual assistant, works in persian arabic russian/firousi and english+turkish (4 ways)
Users can chat with A medicalLLM, provided by dr7 openai completions, baichuan-m3
there is also a VLM to analyze and ocr medical info when needed, or ocr pdfs etc.
There is also an option for user to start with speech to text, instead of typing, model here is openrouter, google/gemini-3.5-flash open ai style both for vllm and stt, (ofc front just calls this gets text and calls normal chat api dont overthink it)
For now Rag / Knowledge is only admin specific, so admin can upload medical guidelines like ACR, user only has images and files attached to a session at a time. No global manipulation of knowledge 
admin should also have a setting and monitoring panel
monitoring can should have seeing signed user changes, active users and their emails used for registeration, full names
chats done today, chats done overall, active users, online users (with caveats), if possble also recent topics if possible to mark by the system

## Roles

For now we have 2
- **User**: registers, chats, upload files/images, no personal knowledge for now
registeration has email, full name and password, possiblity for change passwd is also needed
- **Admin**: shared knowledge base CRUD, user management, usage stats, system settings as we spoke before

## Architecture

FastAPI backend with PostgreSQL, images/files can be s3, debateable
and a vector database (i lean towards quadrant and milvus if good, note that i have arabic, has norm challenges, also persian).
for matching i want to use bge-m3 with hybrid, so dense and sparse, i think vector dbs support is, so i do no searching implementation myself (again call openrouter here assuming i have the key)
Auth we can do oauth2 register then jwt refresh, for admin tho lets do a apikey, x-api-key, if safe, if not debate. 
Code will be fully agentic, LangChain agent with tool-calling, skill system, and RAG. Three prompt languages are driven entirely by prompt content.
Lets just consider that i like code with more abstractions used from people, rather than having higher LOC

## Structure

as a suggestion i d like it to be like this:
├── AGENTS.md # detailed description
├── api # fastapi, routers
├── core # anything we implement
├── data # extra storage if need be
├── db # db connectors
├── docker-compose.yml
├── Dockerfile
├── docs # if any extra md files are required, other than prompts
├── models # db models
├── opencode.json # opencode json for agent, restrict acces to env vars, bash, make ai ask
├── prompts # where prompts md files live
├── pyproject.toml # toml with uv
├── README.md # short readme on how to run, start dev ing
├── schemas # pydantic of models
├── scripts # if need be for testing utils you name it
├── services # controller like style here, llm calls, idk
├── skills # obvious
└── uv.lock


## Features

- Registration/login/profile management
- Chat sessions (create, list, history, soft-delete)
- AI agent with tools: RAG search (user + general), VLM image analysis, OCR (PDFs/images)
- File uploads to object storage
- STT
- Personal knowledge base (upload → chunk → embed → vector store) (per chat only user data is only in chat, not persisted for many sessions)
- Skills system (progressive-disclosure markdown files)
- Admin: knowledge base CRUD, vector search testing, user management, usage analytics
- Admin: system settings (key-value config toggles)
- Multi-language prompts in all aformentioned languages

## Data Stores

- **PostgreSQL**: users, sessions, messages, uploads, knowledge entries, settings
- **S3-compatible object store**: uploaded files (or anything easier i dont care)
- **Vector DB**: user document chunks (scoped) + general knowledge base (shared) ( do we even need user chunks if its per session ?)

## Endpoint Groups

- `/auth/*` — register, login
- `/profile` — view/update profile
- `/sessions/*` — session CRUD, messages (agent chat)
- `/chat/image`, `/stt`, `/tts` — media processing
- `/uploads/*` — file upload CRUD
- `/knowledge/*` — personal knowledge base
- `/admin/*` — knowledge, users, stats, settings

## Key Design Points

- Tool errors returned as text (not exceptions) for agent self-correction
- Recursion limit on agent tool loops
- Prompts loaded from markdown files, cached in memory
- Skills with YAML frontmatter (frontmatter stripped before use)
- Tables created from ORM on startup, no migrations for now


Anything i have put here aside from main features
is challenge able, do dont just aggree with me, lets debate, make a good design, then start implementing only after