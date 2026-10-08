# SQL Injection (CWE-89)

SQL injection happens when untrusted input is concatenated or interpolated directly into a SQL query string, letting an attacker change the query's logic. A classic vulnerable pattern in Python:

```python
query = "SELECT * FROM users WHERE name = '" + username + "'"
cursor.execute(query)
```

An attacker supplying `username = "' OR '1'='1"` turns the WHERE clause into something that matches every row.

## Prevention: parameterized queries

The fix is to let the database driver bind parameters separately from the query text, never to concatenate:

```python
query = "SELECT * FROM users WHERE name = %s"
cursor.execute(query, (username,))
```

This applies the same way across `sqlite3`, `psycopg2`, and most DB-API 2.0-compliant drivers: pass placeholders (`%s`, `?`, or named parameters depending on the driver) and a separate parameter tuple, never an f-string or `.format()` call into the SQL text.

## Related

String-built SQL is the issue regardless of whether it uses `+`, f-strings, or `%`. ORMs (SQLAlchemy, Django ORM) are not automatically safe either if raw SQL fragments are still built by concatenation inside `.raw()` or `text()` calls with unescaped input.
