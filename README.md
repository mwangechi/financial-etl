[Back to Portfolio](https://mwangechi.github.io/mwangechi.github.io/)

# Automated ETL Framework for Financial Data

A containerized, production-ready ETL framework that extracts financial market data from APIs, applies validation and transformation rules, and loads clean datasets into PostgreSQL. Built with extensibility in mind — add new data sources by implementing a simple extractor interface.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐
│   Extract    │────▶│  Validate    │────▶│  Transform   │────▶│    Load    │
│  (API/CSV)   │     │  (Quality)   │     │  (Business)  │     │ (Postgres) │
└──────────────┘     └──────────────┘     └──────────────┘     └────────────┘
       │                    │                    │                    │
       └────────────────────┴────────────────────┴────────────────────┘
                              Pipeline Orchestrator
```

## Features

- **Modular ETL**: Clean separation of Extract, Transform, Load stages
- **Data Quality**: Schema validation, null checks, range validation, duplicate detection
- **Extensible Extractors**: Interface-based design for adding new data sources
- **Retry Logic**: Configurable retries with exponential backoff for API calls
- **Containerized**: Full Docker Compose setup with PostgreSQL
- **Comprehensive Logging**: Structured logging with per-run log files
- **Idempotent Loads**: Upsert strategy prevents duplicate records

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Database | PostgreSQL 15 |
| Containerization | Docker & Docker Compose |
| Data Validation | Custom validators |
| HTTP Client | requests + tenacity (retry) |
| Data Processing | pandas |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)

### 1. Clone & Configure

```bash
git clone https://github.com/wamahua/financial-etl.git
cd financial-etl
cp .env.example .env
```

### 2. Start with Docker Compose

```bash
# Build and start everything
docker compose up -d

# Check logs
docker compose logs -f etl
```

### 3. Run Locally (without Docker)

```bash
pip install -r requirements.txt

# Initialize the database schema
python3 -m src.pipeline --init-db

# Run the full ETL pipeline
python3 -m src.pipeline
```

### 4. Run Tests

```bash
python3 -m pytest tests/ -v
```

### 5. Using the Makefile

```bash
make build       # Build Docker image
make up          # Start services
make run         # Run ETL pipeline
make test        # Run test suite
make logs        # Tail logs
make clean       # Stop and remove containers
```

## Project Structure

```
financial-etl/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── Makefile
├── .env.example
├── .gitignore
├── config/
│   └── etl_config.yaml
├── src/
│   ├── __init__.py
│   ├── pipeline.py              # Main orchestrator
│   ├── utils.py                 # Logging, config helpers
│   ├── extract/
│   │   ├── __init__.py
│   │   └── api_extractor.py     # API data extraction
│   ├── transform/
│   │   ├── __init__.py
│   │   └── data_transformer.py  # Business transformations
│   ├── load/
│   │   ├── __init__.py
│   │   └── postgres_loader.py   # PostgreSQL loader
│   └── quality/
│       ├── __init__.py
│       └── validators.py        # Data quality checks
├── schemas/
│   └── create_tables.sql
└── tests/
    ├── __init__.py
    ├── test_extractor.py
    ├── test_transformer.py
    └── test_loader.py
```

## Configuration

Edit `config/etl_config.yaml` or override via environment variables in `.env`.

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_DB` | Database name | `financial` |
| `API_BASE_URL` | Financial data API | Alpha Vantage |
| `API_KEY` | API authentication key | `demo` |
| `BATCH_SIZE` | Records per insert batch | `1000` |

## License

MIT
