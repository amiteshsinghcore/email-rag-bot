# PST Email RAG Bot

## Welcome

The PST Email RAG Bot is an intelligent system for analyzing Outlook email archives (PST files) using advanced Retrieval-Augmented Generation (RAG) technology.

## Key Features

### 🚀 High-Performance Processing
- Processes 10GB+ PST files in ~20 minutes (7.5x speedup)
- Multi-core parallel processing
- Async I/O pipeline for maximum throughput

### 🧠 Intelligent Query Engine
- **7 Query Types**: Simple lookup, summarization, chronological, analytical, comparative, trend analysis, entity extraction
- **Query Enrichment**: LLM-powered query expansion with HyDE and multi-query retrieval
- **Automatic Relationship Discovery**: Finds contradictions, decision evolution, missing context

### 🔍 Forensic & Investigation
- SHA-256 hash verification and chain of custody
- Email header analysis (SPF/DKIM/DMARC spoofing detection)
- Network graph analysis and timeline reconstruction
- PII detection and attorney-client privilege filtering

### 💬 Real-Time Activity Display
- Claude Code-style streaming activity feed
- Character-by-character progress updates
- WebSocket-based real-time status

### 🔌 Multi-LLM Support
- Custom endpoint support
- OpenAI (GPT-4, GPT-3.5)
- Anthropic Claude
- Google Gemini
- xAI Grok

## Quick Start

```bash
# Install dependencies
pip install -r backend/requirements.txt
cd frontend && npm install

# Start services
docker-compose up -d

# Run backend
cd backend && uvicorn app.main:app --reload

# Run frontend
cd frontend && npm run dev
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PST Email RAG System                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │   PST    │───▶│   RAG    │───▶│  React   │             │
│  │  Parser  │    │  Engine  │    │    UI    │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│       │               │                                     │
│       ▼               ▼                                     │
│  ┌──────────┐    ┌──────────┐                             │
│  │PostgreSQL│    │ ChromaDB │                             │
│  │Metadata  │    │ Vectors  │                             │
│  └──────────┘    └──────────┘                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Documentation Sections

- **[Requirements](requirements/overview.md)** - Functional and non-functional requirements
- **[Architecture](architecture/overview.md)** - System design and database schema
- **[Implementation](implementation/tech-stack.md)** - Technology stack and setup
- **[API Reference](api/rest.md)** - REST and WebSocket API documentation
