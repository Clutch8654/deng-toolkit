"""SQL Server metadata adapter using INFORMATION_SCHEMA and system views."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl


@dataclass
class SQLServerAdapter:
    """Adapter for extracting metadata from SQL Server databases."""

    conn: Any  # pymssql connection

    def get_tables(self, database: str) -> pl.DataFrame:
        """
        Get all tables with row count estimates.

        Returns DataFrame with: database, schema, table_name, row_count_estimate
        """
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            s.name AS [schema],
            t.name AS table_name,
            CAST(ISNULL(SUM(p.rows), 0) AS BIGINT) AS row_count_estimate
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
        WHERE t.type = 'U'
          AND s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        GROUP BY s.name, t.name
        ORDER BY s.name, t.name;
        """
        return self._execute_query(query)

    def get_columns(self, database: str) -> pl.DataFrame:
        """
        Get all columns with data types.

        Returns DataFrame with: database, schema, table_name, column_name,
                                data_type, is_nullable, ordinal_position
        """
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            c.TABLE_SCHEMA AS [schema],
            c.TABLE_NAME AS table_name,
            c.COLUMN_NAME AS column_name,
            c.DATA_TYPE AS data_type,
            CAST(CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END AS BIT) AS is_nullable,
            CAST(c.ORDINAL_POSITION AS INT) AS ordinal_position,
            CAST(c.CHARACTER_MAXIMUM_LENGTH AS BIGINT) AS max_length,
            CAST(c.NUMERIC_PRECISION AS INT) AS numeric_precision,
            CAST(c.NUMERIC_SCALE AS INT) AS numeric_scale
        FROM INFORMATION_SCHEMA.COLUMNS c
        INNER JOIN INFORMATION_SCHEMA.TABLES t
            ON c.TABLE_SCHEMA = t.TABLE_SCHEMA
            AND c.TABLE_NAME = t.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
          AND c.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION;
        """
        return self._execute_query(query)

    def get_primary_keys(self, database: str) -> pl.DataFrame:
        """
        Get primary key columns.

        Returns DataFrame with: database, schema, table_name, column_name, key_name
        """
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            s.name AS [schema],
            t.name AS table_name,
            c.name AS column_name,
            i.name AS key_name
        FROM sys.indexes i
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        INNER JOIN sys.tables t ON i.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE i.is_primary_key = 1
          AND s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY s.name, t.name, ic.key_ordinal;
        """
        return self._execute_query(query)

    def get_foreign_keys(self, database: str) -> pl.DataFrame:
        """
        Get foreign key relationships.

        Returns DataFrame with: database, schema, table_name, column_name,
                                fk_name, ref_schema, ref_table, ref_column
        """
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            s.name AS [schema],
            t.name AS table_name,
            c.name AS column_name,
            fk.name AS fk_name,
            rs.name AS ref_schema,
            rt.name AS ref_table,
            rc.name AS ref_column
        FROM sys.foreign_key_columns fkc
        INNER JOIN sys.foreign_keys fk ON fkc.constraint_object_id = fk.object_id
        INNER JOIN sys.tables t ON fkc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.columns c ON fkc.parent_object_id = c.object_id AND fkc.parent_column_id = c.column_id
        INNER JOIN sys.tables rt ON fkc.referenced_object_id = rt.object_id
        INNER JOIN sys.schemas rs ON rt.schema_id = rs.schema_id
        INNER JOIN sys.columns rc ON fkc.referenced_object_id = rc.object_id AND fkc.referenced_column_id = rc.column_id
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY s.name, t.name, fkc.constraint_column_id;
        """
        return self._execute_query(query)

    def get_index_usage_stats(self, database: str) -> pl.DataFrame:
        """
        Get last access timestamps from index usage stats.

        Returns DataFrame with: database, schema, table_name, last_user_seek,
                                last_user_scan, last_user_lookup, last_user_update
        """
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            s.name AS [schema],
            t.name AS table_name,
            MAX(ius.last_user_seek) AS last_user_seek,
            MAX(ius.last_user_scan) AS last_user_scan,
            MAX(ius.last_user_lookup) AS last_user_lookup,
            MAX(ius.last_user_update) AS last_user_update
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.dm_db_index_usage_stats ius
            ON t.object_id = ius.object_id
            AND ius.database_id = DB_ID()
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        GROUP BY s.name, t.name
        ORDER BY s.name, t.name;
        """
        return self._execute_query(query)

    def get_all_metadata(self, database: str, include_profile: bool = False, profile_sample_size: int = 1000) -> pl.DataFrame:
        """
        Get complete metadata for a database in a single denormalized DataFrame.

        Returns DataFrame with all columns needed for the catalog:
        - server, database, schema, table_name, column_name
        - data_type, is_nullable, is_primary_key, is_foreign_key
        - fk_references, row_count_estimate, last_modified, scanned_at
        """
        # Get base data
        columns_df = self.get_columns(database)
        tables_df = self.get_tables(database)
        pk_df = self.get_primary_keys(database)
        fk_df = self.get_foreign_keys(database)
        usage_df = self.get_index_usage_stats(database)

        if columns_df.is_empty():
            return pl.DataFrame()

        # Mark primary keys
        pk_cols = pk_df.select(["database", "schema", "table_name", "column_name"]).with_columns(
            pl.lit(True).alias("is_primary_key")
        )

        # Create FK references string
        fk_refs = (
            fk_df.with_columns(
                (pl.col("ref_schema") + "." + pl.col("ref_table") + "." + pl.col("ref_column")).alias(
                    "fk_references"
                )
            )
            .select(["database", "schema", "table_name", "column_name", "fk_references"])
            .with_columns(pl.lit(True).alias("is_foreign_key"))
        )

        # Compute last_modified from usage stats (latest of any access type)
        usage_with_last = usage_df.with_columns(
            pl.max_horizontal(
                pl.col("last_user_seek"),
                pl.col("last_user_scan"),
                pl.col("last_user_lookup"),
                pl.col("last_user_update"),
            ).alias("last_modified")
        ).select(["database", "schema", "table_name", "last_modified"])

        # Join everything together
        result = (
            columns_df
            # Join row counts from tables
            .join(
                tables_df.select(["database", "schema", "table_name", "row_count_estimate"]),
                on=["database", "schema", "table_name"],
                how="left",
            )
            # Join primary key flags
            .join(pk_cols, on=["database", "schema", "table_name", "column_name"], how="left")
            # Join foreign key refs
            .join(fk_refs, on=["database", "schema", "table_name", "column_name"], how="left")
            # Join usage stats
            .join(usage_with_last, on=["database", "schema", "table_name"], how="left")
            # Fill nulls and add timestamp
            .with_columns(
                [
                    pl.col("is_primary_key").fill_null(False),
                    pl.col("is_foreign_key").fill_null(False),
                    pl.col("fk_references").fill_null(""),
                    pl.col("row_count_estimate").fill_null(0),
                    pl.lit(datetime.now()).alias("scanned_at"),
                ]
            )
        )

        # Optionally add profiling data
        if include_profile:
            print(f"      Running data profiling (sample size: {profile_sample_size})...")
            profile_df = self.get_column_profiles(database, sample_size=profile_sample_size)
            if not profile_df.is_empty():
                result = result.join(
                    profile_df.select([
                        "database", "schema", "table_name", "column_name",
                        "null_count", "null_rate", "distinct_count", "profiled_rows"
                    ]),
                    on=["database", "schema", "table_name", "column_name"],
                    how="left",
                ).with_columns([
                    pl.col("null_count").fill_null(0),
                    pl.col("null_rate").fill_null(0.0),
                    pl.col("distinct_count").fill_null(0),
                    pl.col("profiled_rows").fill_null(0),
                ])
            else:
                # Add empty profile columns
                result = result.with_columns([
                    pl.lit(0).alias("null_count"),
                    pl.lit(0.0).alias("null_rate"),
                    pl.lit(0).alias("distinct_count"),
                    pl.lit(0).alias("profiled_rows"),
                ])

        # Select final columns in order
        base_cols = [
            "database",
            "schema",
            "table_name",
            "column_name",
            "data_type",
            "is_nullable",
            "is_primary_key",
            "is_foreign_key",
            "fk_references",
            "row_count_estimate",
            "last_modified",
            "scanned_at",
        ]

        if include_profile:
            base_cols.extend(["null_count", "null_rate", "distinct_count", "profiled_rows"])

        result = result.select(base_cols)

        return result

    def get_column_profiles(self, database: str, sample_size: int = 1000) -> pl.DataFrame:
        """
        Get column-level data profiles including null rates and distinct counts.

        This is a heavier operation that queries actual table data.

        Args:
            database: Database name
            sample_size: Max rows to sample for profiling (0 = full scan, not recommended)

        Returns:
            DataFrame with: database, schema, table_name, column_name,
                           null_count, null_rate, distinct_count, min_value, max_value, sample_values
        """
        # First get list of tables and columns
        columns_df = self.get_columns(database)
        if columns_df.is_empty():
            return pl.DataFrame()

        results = []
        cursor = self.conn.cursor(as_dict=True)

        try:
            cursor.execute(f"USE [{database}]")

            # Group by table for efficiency
            tables = columns_df.select(["schema", "table_name"]).unique()

            for table_row in tables.iter_rows(named=True):
                schema = table_row["schema"]
                table = table_row["table_name"]

                # Get columns for this table
                table_cols = columns_df.filter(
                    (pl.col("schema") == schema) &
                    (pl.col("table_name") == table)
                )

                # Build dynamic SQL for column stats
                col_stats = []
                col_names = []
                for col_row in table_cols.iter_rows(named=True):
                    col_name = col_row["column_name"]
                    data_type = col_row["data_type"].lower()

                    # Skip large/complex types that can't be easily profiled
                    if data_type in ("xml", "image", "varbinary", "binary", "geography", "geometry", "hierarchyid"):
                        continue

                    col_names.append(col_name)

                    # Safe column name for SQL
                    safe_col = f"[{col_name}]"

                    col_stats.append(f"""
                        SUM(CASE WHEN {safe_col} IS NULL THEN 1 ELSE 0 END) AS [{col_name}_null_count],
                        COUNT(DISTINCT {safe_col}) AS [{col_name}_distinct]
                    """)

                if not col_stats:
                    continue

                # Build and execute profile query with sampling
                stats_sql = ",\n".join(col_stats)
                if sample_size > 0:
                    query = f"""
                        SELECT COUNT(*) as total_rows, {stats_sql}
                        FROM (SELECT TOP {sample_size} * FROM [{schema}].[{table}]) AS sampled
                    """
                else:
                    query = f"""
                        SELECT COUNT(*) as total_rows, {stats_sql}
                        FROM [{schema}].[{table}]
                    """

                try:
                    cursor.execute(query)
                    row = cursor.fetchone()

                    if row:
                        total_rows = row["total_rows"] or 0

                        for col_name in col_names:
                            null_count = row.get(f"{col_name}_null_count", 0) or 0
                            distinct_count = row.get(f"{col_name}_distinct", 0) or 0
                            null_rate = (null_count / total_rows) if total_rows > 0 else 0.0

                            results.append({
                                "database": database,
                                "schema": schema,
                                "table_name": table,
                                "column_name": col_name,
                                "profiled_rows": total_rows,
                                "null_count": null_count,
                                "null_rate": round(null_rate, 4),
                                "distinct_count": distinct_count,
                            })
                except Exception as e:
                    # Log but continue on individual table failures
                    print(f"      Profile failed for {schema}.{table}: {e}")

        finally:
            cursor.close()

        if not results:
            return pl.DataFrame()

        return pl.DataFrame(results)

    def _execute_query(self, query: str) -> pl.DataFrame:
        """Execute SQL query and return results as Polars DataFrame."""
        cursor = self.conn.cursor(as_dict=True)
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            if not rows:
                return pl.DataFrame()
            # Use infer_schema_length=None to scan all rows for consistent schema
            df = pl.DataFrame(rows, infer_schema_length=None)
            return df
        finally:
            cursor.close()


def get_accessible_databases(conn: Any, include_patterns: list[str] | None = None) -> list[str]:
    """
    Get list of accessible databases on the server.

    Args:
        conn: pymssql connection
        include_patterns: List of database names or "*" for all

    Returns:
        List of database names
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT name
            FROM sys.databases
            WHERE state = 0  -- ONLINE
              AND name NOT IN ('master', 'tempdb', 'model', 'msdb')
            ORDER BY name;
        """)
        all_dbs = [row[0] for row in cursor.fetchall()]

        if include_patterns is None or "*" in include_patterns:
            return all_dbs

        # Filter to matching databases
        return [db for db in all_dbs if db in include_patterns]
    finally:
        cursor.close()
