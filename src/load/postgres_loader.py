"""
PostgreSQL Loader.

Handles connection management, table creation, and idempotent
upsert/append loading of DataFrames into PostgreSQL.
"""

import logging
from contextlib import contextmanager
from typing import Generator

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("financial_etl.load")


class PostgresLoader:
    """Loads DataFrames into PostgreSQL with upsert support."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "financial",
        user: str = "etl_user",
        password: str = "changeme_in_production",
        batch_size: int = 1000,
    ) -> None:
        self.connection_url = (
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
        )
        self.batch_size = batch_size
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        """Lazy-initialise SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self.connection_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
            logger.info("Database engine created")
        return self._engine

    @contextmanager
    def connection(self) -> Generator:
        """Context manager for a database connection."""
        conn = self.engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self, schema_path: str = "schemas/create_tables.sql") -> None:
        """Run the schema initialisation SQL script."""
        with open(schema_path, "r") as f:
            sql = f.read()

        with self.connection() as conn:
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))

        logger.info("Schema initialised from %s", schema_path)

    def load_append(
        self, df: pd.DataFrame, table_name: str
    ) -> int:
        """
        Append DataFrame rows to the target table.

        Returns the number of rows inserted.
        """
        if df.empty:
            logger.warning("Empty DataFrame — nothing to load into %s", table_name)
            return 0

        rows = 0
        for start in range(0, len(df), self.batch_size):
            batch = df.iloc[start : start + self.batch_size]
            batch.to_sql(
                table_name,
                self.engine,
                if_exists="append",
                index=False,
                method="multi",
            )
            rows += len(batch)
            logger.debug("Loaded batch %d–%d into %s", start, start + len(batch), table_name)

        logger.info("Appended %d rows to %s", rows, table_name)
        return rows

    def load_upsert(
        self,
        df: pd.DataFrame,
        table_name: str,
        conflict_columns: list[str],
        update_columns: list[str] | None = None,
    ) -> int:
        """
        Upsert DataFrame rows using INSERT … ON CONFLICT DO UPDATE.

        Args:
            df: Data to upsert.
            table_name: Target table.
            conflict_columns: Columns forming the unique constraint.
            update_columns: Columns to update on conflict.
                            Defaults to all non-conflict columns.

        Returns:
            Number of rows processed.
        """
        if df.empty:
            logger.warning("Empty DataFrame — nothing to upsert into %s", table_name)
            return 0

        if update_columns is None:
            update_columns = [c for c in df.columns if c not in conflict_columns]

        columns = list(df.columns)
        col_list = ", ".join(columns)
        placeholders = ", ".join([f":{c}" for c in columns])
        conflict_list = ", ".join(conflict_columns)
        update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_columns])

        upsert_sql = text(
            f"INSERT INTO {table_name} ({col_list}) "  # noqa: S608
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_list}) "
            f"DO UPDATE SET {update_set}"
        )

        rows = 0
        with self.connection() as conn:
            for start in range(0, len(df), self.batch_size):
                batch = df.iloc[start : start + self.batch_size]
                records = batch.to_dict(orient="records")
                conn.execute(upsert_sql, records)
                rows += len(records)

        logger.info("Upserted %d rows into %s", rows, table_name)
        return rows

    def load(
        self,
        df: pd.DataFrame,
        table_name: str,
        strategy: str = "upsert",
        conflict_columns: list[str] | None = None,
    ) -> int:
        """
        Load data using the specified strategy.

        Strategies: 'append', 'upsert', 'replace'.
        """
        if strategy == "append":
            return self.load_append(df, table_name)
        elif strategy == "upsert":
            if not conflict_columns:
                raise ValueError("conflict_columns required for upsert strategy")
            return self.load_upsert(df, table_name, conflict_columns)
        elif strategy == "replace":
            with self.connection() as conn:
                conn.execute(text(f"TRUNCATE TABLE {table_name}"))  # noqa: S608
            return self.load_append(df, table_name)
        else:
            raise ValueError(f"Unknown load strategy: {strategy}")

    def close(self) -> None:
        """Dispose the engine and release connections."""
        if self._engine:
            self._engine.dispose()
            logger.info("Database engine disposed")
