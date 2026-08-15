---
name: hp-kb-operations
description: HP knowledge base daily operations — start/stop PG, ingest data, search, check status. Use when the user needs to interact with the HP KB server.
---

# HP Knowledge Base Operations

## When to Use This Skill
- User says "start PG" / "stop PG" / "检查知识库状态"
- User needs to import documents into the KB
- User needs to search the KB
- User asks about KB status or health

## Prerequisites
- SSH access to hp@hp (passwordless key)
- Source: `set -a; source /data/knowledge/.env; set +a`
- Python venv: `/data/ai-venv/bin/activate`

## Operations

### Start PostgreSQL
```bash
ssh hp@hp "/home/hp/.local/pg18/start.sh"
```

### Stop PostgreSQL
```bash
ssh hp@hp "/home/hp/.local/pg18/stop.sh"
```

### Check PG Status
```bash
ssh hp@hp "pg_isready -h 127.0.0.1 -p 5432"
```

### Search Knowledge Base
```bash
ssh hp@hp "source /data/ai-venv/bin/activate && set -a && source /data/knowledge/.env && set +a && python /data/knowledge/pipeline/search.py '<query>' --top-k 10"
```

### Ingest Documents
```bash
ssh hp@hp "source /data/ai-venv/bin/activate && set -a && source /data/knowledge/.env && set +a && python /data/knowledge/pipeline/ingest.py <domain> <project> <path> --level N --tags t1,t2"
```

### Check Document Counts
```bash
ssh hp@hp "source /data/ai-venv/bin/activate && PGPASSFILE=/data/knowledge/.pgpass psql -h 127.0.0.1 -U knowledge -d knowledge -c \"SELECT domain, project, COUNT(*) FROM chunks GROUP BY domain, project ORDER BY domain, project;\""
```

### View Recent Import Logs
```bash
ssh hp@hp "tail -50 /data/knowledge/logs/ingest.log 2>/dev/null || echo '(no ingest log yet)'"
```

### Check MCP Server Status
```bash
ssh hp@hp "ps aux | grep mcp-server | grep -v grep || echo 'MCP server not running (will start on demand via SSH)'"
```

## Notes
- PG18 data dir: `/data/pg-knowledge`
- KB code dir: `/data/knowledge/pipeline/`
- .env file: `/data/knowledge/.env` (chmod 600)
- .pgpass file: `/data/knowledge/.pgpass` (chmod 600)
- Bad xlsx files are auto-skipped (zipfile.BadZipFile / InvalidFileException / OSError)
