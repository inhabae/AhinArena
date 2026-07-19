# Operations and telemetry

## Structured logs and correlation

API and worker telemetry is emitted as one JSON object per line to standard
output. Ship standard output to the central log system; do not scrape
containers for log files. Every API response includes `X-Request-ID`. Clients
may supply a value of at most 128 characters in that header, otherwise the API
generates a UUID. The request ID appears on `api_request_completed` and related
API events, including `match_job_enqueued`.

Worker events use `job_id` to correlate queue and execution activity with the
API enqueue event. Important event names are `worker_started`,
`worker_heartbeat`, `match_job_claimed`, `match_job_retried`,
`match_job_completed`, and `match_job_failed`. Completion and failure events
include `match_duration_ms`; heartbeats include queued and running job counts.

Do not treat logs as a source of game moves, request bodies, bot source or
executables, sandbox commands, session IDs, email addresses, credentials, or
database URLs. The application logs method and path only (not query strings),
and worker failures log an exception type plus job context rather than an
exception message or traceback. Configure the log collector to redact
authorization headers, cookies, `DATABASE_URL`, API keys, and tokens from any
infrastructure logs before indexing.

## Dashboard recommendations

Build an operations dashboard from structured log events with these panels:

1. API request volume, 4xx/5xx rate, and p50/p95/p99 `duration_ms`, grouped by
   method and path.
2. Current `queue_depth` and `running_jobs` from `worker_heartbeat`, plus the
   age of the oldest queued `match_jobs` row from PostgreSQL.
3. Claimed, completed, retried, and failed job counts by game and attempt.
4. p50/p95/p99 `match_duration_ms`, grouped by game, and a breakdown of
   `failure_reason`/`error_type` for failed jobs.
5. Worker-start count and time since the most recent heartbeat for every worker
   replica.

## Alert recommendations

Tune thresholds to observed traffic, then alert on sustained conditions:

- API 5xx rate above 2% for 10 minutes, or p95 API duration above the service
  objective for 15 minutes.
- No worker heartbeat for two heartbeat intervals plus five minutes.
- Queue depth above normal capacity, or oldest queued job age above five
  minutes, for 10 minutes.
- Any `match_job_failed` with `failure_reason=stalled_max_attempts`, and a
  match execution failure rate above 5% for 15 minutes.
- PostgreSQL readiness failures or an unhealthy API container for more than two
  minutes.

## Retention and access

Keep high-volume request and heartbeat logs for 30 days, and retain aggregated
operational metrics for at least 13 months to support capacity planning and
seasonal comparisons. Retain security-relevant audit/export records according
to the organization's policy, separately from application telemetry. Restrict
raw-log access to operators who need it, encrypt logs in transit and at rest,
and regularly test deletion and redaction workflows.
