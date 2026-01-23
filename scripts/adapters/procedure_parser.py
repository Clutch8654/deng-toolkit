"""
SQL Procedure Parser - Extract patterns from T-SQL procedures using sqlglot.

Extracts:
- JOIN patterns: Table relationships with join conditions
- Aggregation patterns: SUM, COUNT, AVG usage per column
- Filter patterns: Common WHERE clause conditions
- Metric formulas: Business calculations (ratios, percentages)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JoinPattern:
    """Represents a JOIN relationship between tables."""

    left_table: str
    right_table: str
    join_type: str  # INNER, LEFT, RIGHT, FULL, CROSS
    on_columns: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "leftTable": self.left_table,
            "rightTable": self.right_table,
            "joinType": self.join_type,
            "onColumns": [list(c) for c in self.on_columns],
        }


@dataclass
class AggregationPattern:
    """Represents an aggregation function usage."""

    function: str  # SUM, COUNT, AVG, MIN, MAX
    column: str
    alias: str | None = None
    context: str | None = None  # Table or subquery name

    def to_dict(self) -> dict:
        return {
            "function": self.function,
            "column": self.column,
            "alias": self.alias,
            "context": self.context,
        }


@dataclass
class FilterPattern:
    """Represents a WHERE clause condition."""

    column: str
    operator: str  # =, IN, BETWEEN, >, <, LIKE, IS NULL, etc.
    value_pattern: str  # Literal value, parameter, or pattern description

    def to_dict(self) -> dict:
        return {
            "column": self.column,
            "operator": self.operator,
            "valuePattern": self.value_pattern,
        }


@dataclass
class MetricFormula:
    """Represents a discovered metric/calculation."""

    name: str | None  # From alias or column name
    formula: str  # Raw SQL expression
    columns_used: list[str] = field(default_factory=list)
    is_ratio: bool = False  # Contains division

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "formula": self.formula,
            "columnsUsed": self.columns_used,
            "isRatio": self.is_ratio,
        }


@dataclass
class ParsedProcedure:
    """Complete parsed analysis of a SQL procedure."""

    joins: list[JoinPattern] = field(default_factory=list)
    aggregations: list[AggregationPattern] = field(default_factory=list)
    filters: list[FilterPattern] = field(default_factory=list)
    metrics: list[MetricFormula] = field(default_factory=list)
    tables_referenced: set[str] = field(default_factory=set)
    columns_referenced: set[str] = field(default_factory=set)
    parse_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "joinPatterns": [j.to_dict() for j in self.joins],
            "aggregations": [a.to_dict() for a in self.aggregations],
            "filters": [f.to_dict() for f in self.filters],
            "discoveredMetrics": [m.to_dict() for m in self.metrics],
            "tablesReferenced": list(self.tables_referenced),
            "columnsReferenced": list(self.columns_referenced),
            "complexity": {
                "tables": len(self.tables_referenced),
                "joins": len(self.joins),
                "aggregations": len(self.aggregations),
                "filters": len(self.filters),
                "metrics": len(self.metrics),
            },
        }


class ProcedureParser:
    """Parse T-SQL procedures to extract patterns using sqlglot."""

    def __init__(self):
        try:
            import sqlglot
            from sqlglot import exp

            self.sqlglot = sqlglot
            self.exp = exp
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        """Check if sqlglot is available."""
        return self._available

    def parse(self, sql: str) -> ParsedProcedure:
        """Parse SQL and return structured analysis."""
        result = ParsedProcedure()

        if not self._available:
            result.parse_errors.append("sqlglot not available")
            return result

        if not sql or not sql.strip():
            result.parse_errors.append("Empty SQL")
            return result

        # Try to parse with T-SQL dialect
        try:
            statements = self.sqlglot.parse(sql, dialect="tsql", error_level="IGNORE")
        except Exception as e:
            result.parse_errors.append(f"Parse error: {str(e)[:200]}")
            return result

        for stmt in statements:
            if stmt is None:
                continue
            try:
                self._extract_from_statement(stmt, result)
            except Exception as e:
                result.parse_errors.append(f"Analysis error: {str(e)[:200]}")

        return result

    def _extract_from_statement(self, stmt: Any, result: ParsedProcedure) -> None:
        """Extract all patterns from a single statement."""
        # Extract joins
        self._extract_joins(stmt, result)

        # Extract aggregations
        self._extract_aggregations(stmt, result)

        # Extract filters
        self._extract_filters(stmt, result)

        # Extract metrics (ratios/calculations)
        self._extract_metrics(stmt, result)

        # Extract table and column references
        self._extract_references(stmt, result)

    def _extract_joins(self, stmt: Any, result: ParsedProcedure) -> None:
        """Find all JOIN clauses and their conditions."""
        exp = self.exp

        for join in stmt.find_all(exp.Join):
            try:
                join_type = "INNER"  # Default
                if join.side:
                    join_type = join.side.upper()
                elif join.kind:
                    join_type = join.kind.upper()

                # Get the joined table
                right_table = self._get_table_name(join.this)

                # Try to find the left table from parent FROM clause
                left_table = None
                parent = join.parent
                if parent and hasattr(parent, "this"):
                    left_table = self._get_table_name(parent.this)

                if not right_table:
                    continue

                # Extract ON conditions
                on_columns = []
                on_clause = join.args.get("on")
                if on_clause:
                    on_columns = self._extract_join_conditions(on_clause)

                pattern = JoinPattern(
                    left_table=left_table or "UNKNOWN",
                    right_table=right_table,
                    join_type=join_type,
                    on_columns=on_columns,
                )
                result.joins.append(pattern)
            except Exception:
                pass  # Skip malformed joins

    def _extract_join_conditions(self, on_clause: Any) -> list[tuple[str, str]]:
        """Extract column pairs from JOIN ON clause."""
        exp = self.exp
        conditions = []

        # Handle EQ comparisons in ON clause
        for eq in on_clause.find_all(exp.EQ):
            try:
                left = eq.this
                right = eq.expression

                left_col = self._get_column_name(left)
                right_col = self._get_column_name(right)

                if left_col and right_col:
                    conditions.append((left_col, right_col))
            except Exception:
                pass

        return conditions

    def _extract_aggregations(self, stmt: Any, result: ParsedProcedure) -> None:
        """Find SUM, COUNT, AVG, etc. with target columns."""
        exp = self.exp

        agg_funcs = {
            exp.Sum: "SUM",
            exp.Count: "COUNT",
            exp.Avg: "AVG",
            exp.Min: "MIN",
            exp.Max: "MAX",
        }

        for agg_type, func_name in agg_funcs.items():
            for agg in stmt.find_all(agg_type):
                try:
                    # Get the column being aggregated
                    if agg.this:
                        if isinstance(agg.this, exp.Star):
                            column = "*"
                        else:
                            column = self._get_column_name(agg.this) or str(agg.this)
                    else:
                        column = "*"

                    # Get alias if present
                    alias = None
                    parent = agg.parent
                    if isinstance(parent, exp.Alias):
                        alias = str(parent.alias)

                    # Try to get context (table name)
                    context = None
                    if hasattr(agg.this, "table"):
                        context = agg.this.table

                    pattern = AggregationPattern(
                        function=func_name,
                        column=column,
                        alias=alias,
                        context=context,
                    )
                    result.aggregations.append(pattern)
                except Exception:
                    pass

    def _extract_filters(self, stmt: Any, result: ParsedProcedure) -> None:
        """Find WHERE conditions and their columns."""
        exp = self.exp

        for where in stmt.find_all(exp.Where):
            self._extract_filter_conditions(where.this, result)

    def _extract_filter_conditions(self, condition: Any, result: ParsedProcedure) -> None:
        """Recursively extract filter conditions."""
        exp = self.exp

        if condition is None:
            return

        # Handle different condition types
        try:
            if isinstance(condition, exp.EQ):
                self._add_filter(condition, "=", result)
            elif isinstance(condition, exp.NEQ):
                self._add_filter(condition, "!=", result)
            elif isinstance(condition, exp.GT):
                self._add_filter(condition, ">", result)
            elif isinstance(condition, exp.GTE):
                self._add_filter(condition, ">=", result)
            elif isinstance(condition, exp.LT):
                self._add_filter(condition, "<", result)
            elif isinstance(condition, exp.LTE):
                self._add_filter(condition, "<=", result)
            elif isinstance(condition, exp.In):
                self._add_in_filter(condition, result)
            elif isinstance(condition, exp.Between):
                self._add_between_filter(condition, result)
            elif isinstance(condition, exp.Like):
                self._add_filter(condition, "LIKE", result)
            elif isinstance(condition, exp.Is):
                self._add_is_filter(condition, result)
            elif isinstance(condition, (exp.And, exp.Or)):
                # Recurse into AND/OR conditions
                self._extract_filter_conditions(condition.this, result)
                self._extract_filter_conditions(condition.expression, result)
        except Exception:
            pass

    def _add_filter(self, condition: Any, operator: str, result: ParsedProcedure) -> None:
        """Add a simple comparison filter."""
        column = self._get_column_name(condition.this)
        if not column:
            return

        value = self._get_value_pattern(condition.expression)
        result.filters.append(FilterPattern(column=column, operator=operator, value_pattern=value))

    def _add_in_filter(self, condition: Any, result: ParsedProcedure) -> None:
        """Add an IN filter."""
        exp = self.exp
        column = self._get_column_name(condition.this)
        if not column:
            return

        # Get IN values
        expressions = condition.expressions
        if expressions:
            values = [self._get_value_pattern(e) for e in expressions[:5]]  # Limit to first 5
            if len(expressions) > 5:
                values.append("...")
            value_pattern = f"({', '.join(values)})"
        else:
            value_pattern = "(subquery)"

        result.filters.append(FilterPattern(column=column, operator="IN", value_pattern=value_pattern))

    def _add_between_filter(self, condition: Any, result: ParsedProcedure) -> None:
        """Add a BETWEEN filter."""
        column = self._get_column_name(condition.this)
        if not column:
            return

        low = self._get_value_pattern(condition.args.get("low"))
        high = self._get_value_pattern(condition.args.get("high"))
        value_pattern = f"{low} AND {high}"

        result.filters.append(FilterPattern(column=column, operator="BETWEEN", value_pattern=value_pattern))

    def _add_is_filter(self, condition: Any, result: ParsedProcedure) -> None:
        """Add an IS NULL/IS NOT NULL filter."""
        column = self._get_column_name(condition.this)
        if not column:
            return

        exp = self.exp
        if isinstance(condition.expression, exp.Null):
            operator = "IS NULL"
            value_pattern = "NULL"
        else:
            operator = "IS"
            value_pattern = str(condition.expression)

        result.filters.append(FilterPattern(column=column, operator=operator, value_pattern=value_pattern))

    def _extract_metrics(self, stmt: Any, result: ParsedProcedure) -> None:
        """Discover ratio/percentage calculations."""
        exp = self.exp

        # Look for division operations (ratios)
        for div in stmt.find_all(exp.Div):
            try:
                formula = div.sql(dialect="tsql")

                # Get alias if present
                name = None
                parent = div.parent
                if isinstance(parent, exp.Alias):
                    name = str(parent.alias)

                # Extract columns used
                columns_used = []
                for col in div.find_all(exp.Column):
                    col_name = self._get_column_name(col)
                    if col_name:
                        columns_used.append(col_name)

                # Check if it looks like a ratio/percentage
                is_ratio = True

                metric = MetricFormula(
                    name=name,
                    formula=formula[:500],  # Limit formula length
                    columns_used=columns_used,
                    is_ratio=is_ratio,
                )
                result.metrics.append(metric)
            except Exception:
                pass

        # Look for CASE expressions with aggregates (common pattern for metrics)
        for case in stmt.find_all(exp.Case):
            try:
                # Check if CASE contains aggregates
                has_agg = any(
                    case.find(agg_type)
                    for agg_type in [exp.Sum, exp.Count, exp.Avg]
                )

                if not has_agg:
                    continue

                formula = case.sql(dialect="tsql")

                # Get alias
                name = None
                parent = case.parent
                if isinstance(parent, exp.Alias):
                    name = str(parent.alias)

                # Extract columns
                columns_used = []
                for col in case.find_all(exp.Column):
                    col_name = self._get_column_name(col)
                    if col_name:
                        columns_used.append(col_name)

                metric = MetricFormula(
                    name=name,
                    formula=formula[:500],
                    columns_used=columns_used,
                    is_ratio=False,
                )
                result.metrics.append(metric)
            except Exception:
                pass

    def _extract_references(self, stmt: Any, result: ParsedProcedure) -> None:
        """Extract all table and column references."""
        exp = self.exp

        # Tables
        for table in stmt.find_all(exp.Table):
            table_name = self._get_table_name(table)
            if table_name:
                result.tables_referenced.add(table_name)

        # Columns
        for col in stmt.find_all(exp.Column):
            col_name = self._get_column_name(col)
            if col_name:
                result.columns_referenced.add(col_name)

    def _get_table_name(self, node: Any) -> str | None:
        """Extract table name from a node."""
        if node is None:
            return None

        exp = self.exp

        if isinstance(node, exp.Table):
            parts = []
            if node.catalog:
                parts.append(str(node.catalog))
            if node.db:
                parts.append(str(node.db))
            if node.name:
                parts.append(str(node.name))
            return ".".join(parts) if parts else None

        if hasattr(node, "name"):
            return str(node.name)

        return str(node) if node else None

    def _get_column_name(self, node: Any) -> str | None:
        """Extract column name from a node."""
        if node is None:
            return None

        exp = self.exp

        if isinstance(node, exp.Column):
            parts = []
            if node.table:
                parts.append(str(node.table))
            if node.name:
                parts.append(str(node.name))
            return ".".join(parts) if parts else None

        if hasattr(node, "name"):
            return str(node.name)

        return None

    def _get_value_pattern(self, node: Any) -> str:
        """Get a description of a value (literal, parameter, etc.)."""
        if node is None:
            return "NULL"

        exp = self.exp

        if isinstance(node, exp.Literal):
            # Return literal value (truncated if long)
            val = str(node.this)
            return val[:50] if len(val) > 50 else val

        if isinstance(node, exp.Parameter):
            return f"@{node.name}" if hasattr(node, "name") else "@param"

        if isinstance(node, exp.Placeholder):
            return "?"

        if isinstance(node, exp.Null):
            return "NULL"

        if isinstance(node, exp.Subquery):
            return "(subquery)"

        # Default: return string representation
        try:
            return str(node)[:50]
        except Exception:
            return "?"
