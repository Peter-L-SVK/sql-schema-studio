# fmt: off
SQL_KEYWORDS = [
    # DML
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "RETURNING",
    # DDL
    "CREATE", "TABLE", "DROP", "ALTER", "ADD", "COLUMN",
    "INDEX", "VIEW", "SEQUENCE", "SCHEMA", "DATABASE", "EXTENSION",
    # Joins
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "NATURAL",
    # Filtering / ordering
    "ON", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "ILIKE",
    "HAVING", "LIMIT", "OFFSET", "DISTINCT", "ALL", "AS",
    "UNION", "INTERSECT", "EXCEPT",
    # Multi-word phrases
    "GROUP BY", "ORDER BY", "ON CONFLICT", "DO NOTHING",
    "IF NOT EXISTS", "IF EXISTS", "OR REPLACE",
    "PRIMARY KEY", "FOREIGN KEY", "REFERENCES",
    "NOT NULL", "NO ACTION", "SET NULL",
    "IS NULL", "IS NOT NULL", "NULLS FIRST", "NULLS LAST",
    "PARTITION BY", "DO UPDATE",
    # Constraints
    "CONSTRAINT", "UNIQUE", "DEFAULT", "NULL", "CHECK",
    "CASCADE", "RESTRICT",
    # Transactions
    "BEGIN", "COMMIT", "ROLLBACK", "TRANSACTION", "SAVEPOINT",
    # Maintenance
    "GRANT", "REVOKE", "TRUNCATE", "EXPLAIN", "ANALYZE",
    "VACUUM", "REINDEX", "CLUSTER",
    # Types
    "INTEGER", "BIGINT", "SMALLINT", "TEXT", "VARCHAR", "CHAR",
    "BOOLEAN", "NUMERIC", "REAL", "FLOAT", "SERIAL", "BIGSERIAL",
    "TIMESTAMP", "TIMESTAMPTZ", "DATE", "TIME",
    "INTERVAL", "JSON", "JSONB", "UUID", "ARRAY", "BYTEA",
    "DOUBLE PRECISION",
    # Logic / values
    "TRUE", "FALSE", "CASE", "WHEN", "THEN", "ELSE", "END",
    "ASC", "DESC",
    # Window functions
    "OVER", "WINDOW", "ROWS", "RANGE",
    # Aggregate / scalar functions
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "COALESCE", "NULLIF", "CAST", "EXTRACT",
    "NOW", "CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME",
    "GENERATE_SERIES", "UNNEST", "STRING_AGG", "ARRAY_AGG",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD",
    # PostgreSQL specific
    "COPY", "LISTEN", "NOTIFY", "LOCK", "INHERITS",
    "TABLESPACE", "OWNER", "TO", "PUBLIC",
    "MATERIALIZED", "TEMPORARY", "TEMP", "UNLOGGED",
    "CONCURRENTLY", "USING", "IMMUTABLE", "STABLE", "VOLATILE",
    "STRICT", "SECURITY", "DEFINER", "INVOKER",
    "SETOF", "COST", "ROWS", "RETURNS",
    "LANGUAGE", "FUNCTION", "TRIGGER", "PROCEDURE",
    "BEFORE", "AFTER", "INSTEAD", "OF", "FOR", "EACH", "ROW", "EXECUTE",
    "DECLARE", "CURSOR", "OPEN", "CLOSE", "FETCH", "RETURN",
    "NEXT", "RECORD", "TYPE", "DOMAIN", "ENUM",
    "GREATEST", "LEAST",
]
# fmt: on
