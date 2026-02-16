"""
ETL Pipeline Orchestrator.

Coordinates the Extract → Validate → Transform → Load flow
for all configured data sources.
"""

import argparse
import logging
import sys
from datetime import datetime

from src.utils import setup_logging, load_config, PipelineContext
from src.extract.api_extractor import StockPriceExtractor, ForexExtractor
from src.transform.data_transformer import DataTransformer
from src.quality.validators import run_quality_checks
from src.load.postgres_loader import PostgresLoader

logger = logging.getLogger("financial_etl.pipeline")


def build_loader(config: dict) -> PostgresLoader:
    """Create a PostgresLoader from config."""
    pg = config["load"]["postgres"]
    return PostgresLoader(
        host=pg["host"],
        port=int(pg["port"]),
        database=pg["database"],
        user=pg["user"],
        password=pg["password"],
        batch_size=int(config["pipeline"].get("batch_size", 1000)),
    )


def run_stock_pipeline(config: dict, ctx: PipelineContext, loader: PostgresLoader) -> None:
    """Execute the stock price ETL pipeline."""
    source_cfg = None
    for s in config["extract"]["sources"]:
        if s["name"] == "daily_stock_prices":
            source_cfg = s
            break

    if source_cfg is None:
        ctx.logger.warning("No daily_stock_prices source configured — skipping")
        return

    # --- Extract ---
    ctx.logger.info("═══ EXTRACT: daily_stock_prices ═══")
    extractor = StockPriceExtractor(
        base_url=source_cfg["base_url"],
        api_key=source_cfg["api_key"],
        symbols=source_cfg["symbols"],
        function=source_cfg.get("function", "TIME_SERIES_DAILY"),
        output_size=source_cfg.get("params", {}).get("outputsize", "compact"),
        timeout=int(source_cfg.get("timeout_seconds", 30)),
        max_retries=int(source_cfg.get("max_retries", 3)),
        rate_limit_per_minute=int(source_cfg.get("rate_limit_per_minute", 5)),
    )

    raw_df = extractor.extract()
    ctx.stats["extracted"] += len(raw_df)

    if raw_df.empty:
        ctx.logger.warning("No stock data extracted — skipping downstream")
        return

    # --- Transform ---
    ctx.logger.info("═══ TRANSFORM: daily_stock_prices ═══")
    transformer = DataTransformer(config.get("transform", {}))
    transformed_df = transformer.transform_stock_prices(raw_df)
    ctx.stats["transformed"] += len(transformed_df)

    # --- Validate ---
    ctx.logger.info("═══ VALIDATE: daily_stock_prices ═══")
    report = run_quality_checks(transformed_df, config.get("quality", {}).get("checks", []))
    ctx.stats["validated"] += len(transformed_df)

    if not report.all_passed:
        ctx.stats["validation_failures"] += report.failure_count
        ctx.logger.warning("Quality checks failed — loading with warnings")

    # --- Load ---
    ctx.logger.info("═══ LOAD: daily_stock_prices ═══")
    strategy = config["load"]["postgres"].get("strategy", "upsert")
    rows = loader.load(
        transformed_df,
        table_name="daily_stock_prices",
        strategy=strategy,
        conflict_columns=["date", "symbol"],
    )
    ctx.stats["loaded"] += rows


def run_forex_pipeline(config: dict, ctx: PipelineContext, loader: PostgresLoader) -> None:
    """Execute the forex rate ETL pipeline."""
    source_cfg = None
    for s in config["extract"]["sources"]:
        if s["name"] == "forex_rates":
            source_cfg = s
            break

    if source_cfg is None:
        ctx.logger.warning("No forex_rates source configured — skipping")
        return

    # --- Extract ---
    ctx.logger.info("═══ EXTRACT: forex_rates ═══")
    extractor = ForexExtractor(
        base_url=source_cfg["base_url"],
        api_key=source_cfg["api_key"],
        pairs=source_cfg["pairs"],
        output_size=source_cfg.get("params", {}).get("outputsize", "compact"),
        timeout=int(source_cfg.get("timeout_seconds", 30)),
        rate_limit_per_minute=int(source_cfg.get("rate_limit_per_minute", 5)),
    )

    raw_df = extractor.extract()
    ctx.stats["extracted"] += len(raw_df)

    if raw_df.empty:
        ctx.logger.warning("No forex data extracted — skipping downstream")
        return

    # --- Transform ---
    ctx.logger.info("═══ TRANSFORM: forex_rates ═══")
    transformer = DataTransformer(config.get("transform", {}))
    transformed_df = transformer.transform_forex_rates(raw_df)
    ctx.stats["transformed"] += len(transformed_df)

    # --- Load ---
    ctx.logger.info("═══ LOAD: forex_rates ═══")
    strategy = config["load"]["postgres"].get("strategy", "upsert")
    rows = loader.load(
        transformed_df,
        table_name="forex_daily_rates",
        strategy=strategy,
        conflict_columns=["date", "pair"],
    )
    ctx.stats["loaded"] += rows


def main() -> None:
    """Main entry point for the ETL pipeline."""
    parser = argparse.ArgumentParser(description="Financial Data ETL Pipeline")
    parser.add_argument("--config", default="config/etl_config.yaml", help="Config file path")
    parser.add_argument("--init-db", action="store_true", help="Initialise database schema and exit")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    log_level = config.get("pipeline", {}).get("log_level", "INFO")
    app_logger = setup_logging(level=log_level)

    # Context
    ctx = PipelineContext(config=config, logger=app_logger)
    app_logger.info("Pipeline started — run_id=%s", ctx.run_id)

    # Loader
    loader = build_loader(config)

    # Schema init mode
    if args.init_db:
        app_logger.info("Initialising database schema…")
        loader.init_schema()
        app_logger.info("Schema initialised. Exiting.")
        loader.close()
        return

    # Run pipelines
    start_time = datetime.now()

    try:
        run_stock_pipeline(config, ctx, loader)
        run_forex_pipeline(config, ctx, loader)
    except Exception as exc:
        app_logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)
    finally:
        loader.close()

    elapsed = (datetime.now() - start_time).total_seconds()
    app_logger.info("Pipeline completed in %.1fs", elapsed)
    app_logger.info(ctx.summary())


if __name__ == "__main__":
    main()
