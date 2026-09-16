# Phase 6.1 — Database and API Performance

Status: first optimization tranche implemented in the working tree.

## Delivered

- Expensive finance/reporting APIs now reject ranges above 366 days and default to 31 days.
- Inventory valuation uses one PostgreSQL `SUM(current_stock * unit_cost)` query.
- Payroll department totals use one grouped PostgreSQL query instead of one query per department.
- Added indexes for paid-order date scans, waiter order history, room-history reporting and folio-date reporting.
- Added PostgreSQL connection health checks, bounded connection age, statement timeout, lock timeout and idle-transaction timeout settings.
- Request observability records request latency, database query count/duration and slow-query counters.

## Baseline procedure

Use production-like PostgreSQL data and record p50/p95/p99 latency, query count, rows returned and error rate. The protected metrics endpoint exposes `http_request_duration`, `database_queries_total` and `database_query_duration_sum_ms`.

```powershell
python manage.py test users.test_phase6_1_performance --settings=core.settings_test
```

Capture `EXPLAIN (ANALYZE, BUFFERS)` for slow queries before adding further indexes, then repeat after each index with the release identifier.

## Runtime configuration

```env
DB_CONN_MAX_AGE=60
DB_STATEMENT_TIMEOUT_MS=30000
DB_LOCK_TIMEOUT_MS=5000
DB_IDLE_TX_TIMEOUT_MS=60000
```

Use PgBouncer or a managed pooler for multi-worker production rather than unbounded application connections. Queries at or above 500ms are counted as slow.

## Remaining measurement gates

- Run production-sized `EXPLAIN (ANALYZE, BUFFERS)` before adding further indexes.
- Compare p95 and query count with the captured baseline after deployment.
- Compare PostgreSQL connection count with `max_connections` and pooler capacity.
- Move reports beyond 366 days to an asynchronous export design.
