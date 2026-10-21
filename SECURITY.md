# Security status

The repository is undergoing a staged self-hosting rebuild. The first foundation patch is **not a production security certification**. Do not expose the legacy stack to untrusted networks until the remaining M0/M1 controls are verified.

Implemented in the foundation patch: API session gate, baseline mutation Origin checks, safe unique orthophoto upload keys, text-only vector popups, private short-lived tile caching and non-cacheable failed tile responses. These are installation-wide sessions; project ACL/RBAC, session revocation and service tokens are not implemented yet.

The second package isolates PostgreSQL connections per short operation, enforces read-only transactions by default, adds transaction-local SQL/idle timeouts and cooperative libpq I/O for gevent. Required route initialization and database bootstrap fail instead of silently reporting success. See [ADR 0002](docs/architecture/0002-isolated-database-transactions.md).

The first-run wizard replaces automatic default account creation. Enrollment is serialized in PostgreSQL, stores a password hash and permanently closes after setup; existing installations stay closed. The local Compose profile generates random secrets and exposes only the app on loopback. Keep an unconfigured installation private until its owner completes setup. Existing legacy accounts are not removed or reset.

Outstanding priorities: replacement of fallback secrets in the legacy deployment; removal of automatic public bucket policies; non-root runtime and private service ports; bounded/streaming original downloads; login throttling; strict configuration validation; durable jobs; actual migration/readiness and backup/restore tests. Published credentials from old installations should be rotated if used. Existing public storage policies are not automatically made private by these patches.

The CLI preflight is intended for an operator inspecting trusted local GeoTIFFs. It is not an isolated parser for hostile uploads. A read-only mount and `--network none` are recommended; production upload processing requires resource-limited isolated workers and additional format validation.

No telemetry is introduced by the foundation patch. The legacy UI still uses external basemaps; a complete offline profile is scheduled separately. See [ROADMAP.md](ROADMAP.md) for release gates and [the original audit](AUDIT_2026-10-20.md) for evidence against the pre-change revision.
