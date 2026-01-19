# Email RAG Bot - Backend

FastAPI backend for the Email RAG Bot application.

## Features

- PST file processing and email extraction
- RAG-based email search and analysis
- Multi-LLM support (OpenAI, Anthropic, Google, xAI)
- WebSocket real-time updates
- Celery task queue for background processing

## Development

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Production

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```
