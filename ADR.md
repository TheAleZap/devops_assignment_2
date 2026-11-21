# Architecture Decision Records


## 1. Backend framework and architecture
Date: 2026-09-28
Status: Decided
**Context:** The core feature is an interactive availability calendar where friend groups of 4–10 people mark free days and see the best date windows update live. Taking this into account, I decided that a "reload-per-action" form interface would handle this poorly. 
The app must run as a single process, and its two domains will later be split into separate services.

**Decision:** Build a JSON API with Python and FastAPI (using one APIRouter per feature domain), served by uvicorn from a single `python app.py` command, with a plain HTML/CSS/JavaScript frontend served as static files by the same process.
Alternatives considered: Flask with server-rendered Jinja templates was rejected because every calendar interaction would require a full page reload, undermining the main feature. React was rejected because it requires npm and a second dependency manifest, which the single-manifest constraint forbids, plus a build step the app doesn't need. Django was rejected because its ORM, admin panel and authentication solve problems this app doesn't have.

**Consequences:** Because each domain already communicates through its own API endpoints, splitting them into separate services later mostly means moving routers rather than rewriting logic. The cost is maintaining two languages and handling frontend state in JavaScript myself.


## 2. Scoping Scheduling and Trips as independently modularizable domains
Date: 2026-09-30
Status: Decided
Context: This project has two separate responsibilities: getting a group to agree on dates, and organizing the trip once dates are chosen. Assignment 2 will split the app into separate services, so if the two share code or tables, the split would require rewriting both.

Decision: Scheduling is a generic domain that receives participant names and a trip length and returns ranked date windows, with no information about trips. Trips owns trips, members and tasks. Each domain has its own folder (router, service, repository), its own APIRouter prefix and its own tables, and Trips calls Scheduling only through scheduling/service.py

Alternatives considered: A single trips module with availability stored as part of each trip. Rejected because it would give that module two reasons to change (trip organization and date finding), violating the Single Responsibility Principle, and would make date finding depend on trip tables, so it couldn't be reused for other kinds of group plans or deployed separately without rewriting both the logic and the schema.

Consequences: In Assignment 2, the in-process call from Trips to scheduling.service becomes a single HTTP call, and each domain takes its own tables with it. The cost is some duplicated data: participant names are stored by both domains instead of being shared through a join.


## 3. Cross-domain data references without foreign keys
Date: 2026-09-30
Status: Decided
Context: Both domains must share one SQLite file for now, but Assignment 2 will move them into separate services, each with its own database. Trips needs to know which date poll its dates came from, and availability needs to identify each participant.

Decision: Each domain creates and owns its own tables, using foreign keys only within a domain: across domains, trips.date_poll_id is a plain integer and availability.participant is a text name, with no FOREIGN KEY between them. Availability is stored as one row per participant per free day, with dates "YYYY-MM-DD".

Alternatives considered: Foreign keys from availability to members and from trips to date_polls. Rejected because the database would then enforce links across domains, which breaks as soon as the tables live in separate databases. Storing availability as date ranges was also rejected: overlapping ranges make the date window calculation much harder, while one row per day costs at most about 900 rows per poll at our scale.

Consequences: Each domain can later take its tables with it without schema changes. The cost is that the database no longer guarantees a trip's date_poll_id exists or that a participant name matches a member, so the application must check this, and member names are stored in both domains.



## 4. Testing approach: unit-test the service layer, verify routers manually
Date: 2026-10-04
Status: Decided

Context: The assignment requires at least 70% coverage on the core business logic of both domains, within a one-week build. Almost all of TripSync's logic lives in the service layer: the date-window ranking, input validation, the task-board rules, and the date confirmation between domains.
Decision: Test the service layer with pytest: pure functions directly, and database-backed service functions against a fresh temporary SQLite database per test (the temp_db fixture, using tmp_path and monkeypatch). Coverage is measured over both whole packages, routers included, with python -m pytest --cov=scheduling --cov=trips: 40 tests, 76% total, 100% on every service and repository module, 0% on the routers.

Alternatives considered: Testing the routers with FastAPI's TestClient was rejected for now: it adds a dependency (httpx), and the routers only translate HTTP requests into service calls and errors into status codes, which I verified manually with curl. Excluding the routers from the measurement to report a higher number was also rejected, because reporting the full total is more transparent.

Consequences: Regressions in the business rules (ranking order, task claiming, date-window validation) are caught automatically. A mistake in the routers' error mapping, such as returning 400 instead of 404, would only be caught manually, so router tests with TestClient are the first thing to add next.


## 5. Not building general-purpose polls
Date: 2026-10-04
Status: Decided
Context: The original proposal included polls with deadlines for other group decisions, such as destination or activities, alongside the date finder. The date-window algorithm, the Trips domain and their tests took most of the week, so I had to decide where the remaining time went.
Decision: Not build general polls; the Scheduling domain covers only the date decision (date polls, availability and best windows), and other group decisions stay outside the app for now.
Alternatives considered: Simple approval-vote polls with deadlines inside the Scheduling domain. Rejected because they would add new tables, endpoints and tests without strengthening the core problem: group chats already handle destination votes reasonably well with built-in polls, while matching everyone's dates is exactly where they fail.
Consequences: The time went into testing the core logic and into documentation, and the app does one job well, but groups still have to decide destination and activities elsewhere. Because Scheduling is generic and has no dependency on Trips, polls could be added there later without changing the Trips domain.

## 6. The split: Scheduling and Trips as two services along the ADR-2 seam
Date: 2026-11-16
Status: Decided
**Context:** Assignment 2 requires one service per feature domain, each with its own container and database. ADR-2 placed the seam between Scheduling and Trips, with Trips reaching Scheduling only through scheduling/service.py, in a single function (confirm_dates).

**Decision:** Split along ADR-2's seam unchanged. services/scheduling owns date_polls and availability; services/trips owns trips, members and tasks. The one cross-seam flow, confirming a trip's dates from a poll, stays server side: Trips calls GET /api/scheduling/polls/{id}/windows/{start}, with the base URL from SCHEDULING_URL and a 2-second timeout. If Scheduling is unreachable, Trips returns 503 with a clear message and leaves the trip unchanged; the rest of Trips keeps working.

**Alternatives considered:** Doing this flow client side (the UI fetches the window from Scheduling and posts it to Trips) was rejected because Trips would then store attendance data supplied by the browser without verifying it. Moving the seam was rejected because ADR-2 held: the split needed one new endpoint, and no table had to move across it.

**Consequences:** trips.date_poll_id was already a plain ID with no foreign key (ADR-3), so the split lost no database-level integrity, but Trips can still hold a poll ID that Scheduling no longer recognises. Confirming dates now depends on the network and on Scheduling being up, which is why the call has a timeout and a designed failure.


## 7. Data and migrations: one SQL Server database per service, versioned forward-only migrations
Date: 2026-11-17
Status: Decided
**Context:** Assignment 2 replaces the shared SQLite file with one SQL Server database per service, each reached by its own login, and requires schema changes to be applied in place through versioned migrations that preserve data. A1 created its tables on boot with CREATE TABLE IF NOT EXISTS, which cannot change a table that already holds data.

**Decision:** Each service owns one database (scheduling_db, trips_db) and one login whose database user exists only in that database, with db_ddladmin, db_datareader and db_datawriter roles. On Azure the same split applies (one serverless database per service on one logical server, one login each), created once during setup. db/init.sql creates the local databases and logins idempotently. The schema lives in numbered SQL files (migrations/001_init.sql) applied at startup by a small runner (migrate.py): it records applied files in a schema_migrations table, runs only pending files in name order, and runs each file together with its schema_migrations insert in one transaction, so a migration is either fully applied and recorded or not applied at all. A1's SQLite data was local demo data only, so no data was copied; each database starts from 001_init.sql. Within each service, foreign keys are kept; across the seam, trips.date_poll_id stays a plain ID (as in ADR-3), checked in code when dates are confirmed, because Trips asks Scheduling for the window and a missing poll is rejected. Applied migrations are never edited, and corrections go in a new file. Recovery plan for a bad migration in production: stop deploying, fix forward with a new migration; if the migration destroyed or corrupted data, restore the database to a point in time before the deploy with Azure SQL point-in-time restore and point DATABASE_URL at the restored copy. Because migrations are forward-only, new migrations are written to be backward compatible (for example, adding a column with a default) so the previous image can still run against the new schema.

**Alternatives considered:** Alembic was rejected because it would add SQLAlchemy and Alembic to a codebase that uses plain SQL, and the runner it would replace is about 40 lines I can explain line by line. Keeping CREATE TABLE IF NOT EXISTS on boot was rejected because it cannot alter tables that hold data. Giving each service login db_owner was rejected in favour of the three narrower roles, since a service never needs to manage users or permissions.

**Consequences:** Porting to SQL Server changed the dialect (IDENTITY, NVARCHAR, real DATE and BIT columns, OUTPUT INSERTED.id instead of lastrowid, %s placeholders), and SQL Server refused ON DELETE SET NULL on tasks.claimed_by because deleting a trip would reach tasks by two cascade paths, so that key is NO ACTION; the app never deletes trips or members, so behaviour is unchanged. A dangling date_poll_id remains possible if Scheduling ever deletes a poll. Migrations run at startup, which is safe only because each service runs at most one replica (ADR-8).


## 9. CI pipeline and testing approach
Date: 2026-11-19
Status: Decided
**Context:** Assignment 2 requires a pipeline on every push and pull request that blocks a merge when lint, tests, 70% coverage per service, an image build, or the OpenAPI and system.yaml checks fail, plus a cross-service integration test. In A1 the routers had 0% coverage and two validation bugs (blank names in Scheduling, an unknown poll returning 400) were only found by the grader.

**Decision:** One workflow (.github/workflows/ci.yml) with five jobs. Lint runs ruff. Test runs once per service against a real SQL Server container started in the job, with db/init.sql applied and throwaway passwords generated for that run, and fails below 70% coverage measured on the service package plus db.py and migrate.py (app.py wiring and export_openapi.py are excluded). Contracts regenerates each openapi.json from the code and fails if the committed file differs, validates both documents, validates system.yaml against the provided schema, and runs scripts/check_system_yaml.py, which checks that system.yaml lists exactly the environment variables config.py reads, the right ports and paths, and only cross-service endpoints that exist in the called service's document. Integration starts the whole system with docker compose and runs tests/integration, including stopping Scheduling to check that Trips answers 503 within 12 seconds, stays healthy and leaves the trip unchanged. Build runs only after every other job passes, builds both images and, on main only, pushes them to GHCR tagged with the commit SHA (provenance disabled). Tests are layered: unit tests for business rules, API tests through FastAPI's TestClient for status codes and response shapes (Scheduling stubbed in Trips), and the integration test for the real HTTP call.

**Alternatives considered:** Testing against SQLite was rejected because the SQL Server dialect differs (IDENTITY, OUTPUT INSERTED.id, DATE and BIT columns) and those differences are where bugs hide. A GitHub Actions service container for SQL Server was rejected because its password would have to be written in the workflow file; starting the container in a step lets the password be generated per run and masked. Excluding routers from coverage to reach 70% (my A1 position) was dropped: API tests now cover them, at 94-100%.

**Consequences:** Scheduling reaches about 90% and Trips about 94% coverage, and the A1 bugs now have tests. A run takes about three minutes, mostly starting SQL Server. Running the tests locally empties the local databases, because the fixtures delete every row before each test. The integration test needs Docker, so it runs in CI and locally with compose, not inside the unit test suites.


## 8. Serverless hosting on Azure and living with cold starts
Date: 2026-11-20
Status: Decided
**Context:** Assignment 2 requires a serverless, pay-per-use deployment on my Azure for Students subscription (about 90 EUR of credit), deployed only by the pipeline. Both services must scale to zero and the databases must pause when idle, which means the first request after a quiet period is slow.

**Decision:** Each service runs as an Azure Container App on the Consumption plan with 0 to 1 replicas, 0.25 vCPU and 0.5 GiB, and external HTTPS ingress; CORS is handled in the services' code, with ingress CORS off. Each service has its own Azure SQL serverless database (General Purpose, Gen5, 0.5 to 1 vCore, locally redundant backups) on the free offer, which pauses after 60 minutes and pauses instead of billing if the free allowance runs out. The UI is a Storage static website. Images live in public GHCR packages tagged with the commit SHA. The CD workflow signs in with a managed identity through OIDC (Contributor on the resource group only), so no Azure password exists anywhere. The Log Analytics workspace that the Container Apps environment creates is kept for container logs (free up to 5 GB a month). Everything is in France Central, the allowed region closest to Madrid. Cold starts are handled at every layer: the services retry the database connection with backoff for about a minute (db.py), the UI retries Azure's 503 and failed reads three times and shows a "waking up" message, Trips waits up to 10 seconds for Scheduling instead of 2, and the CD health check waits up to 6 minutes for this commit's SHA.

**Alternatives considered:** A minimum of one replica would remove container cold starts but bills the container all the time, against the pay-per-use requirement. App Service was rejected because its plan is billed even when idle. Private GHCR packages with registry credentials were rejected because they add a secret to manage, while the images contain only code (no .env, no tests) and the repository is already public. Retrying writes in the UI was rejected: a failed POST may already have reached the service, so only reads (GET) are retried and writes show a clear message instead.

**Consequences:** The first request after the database has paused takes up to about a minute and may first get Azure's 503 "App port is not ready", which the UI turns into a retry and a clear message. Idle cost is close to zero. With at most one replica, running migrations at startup is safe (no two instances race), but throughput is capped, which is acceptable for a group trip planner. The 10-second Trips timeout means a slow Scheduling can make confirming dates wait up to 10 seconds before the designed 503.


## 10. Not queuing date confirmations when Scheduling is unavailable
Date: 2026-11-21
Status: Decided (not built)
**Context:** Confirming a trip's dates is the only flow that crosses the seam: Trips calls Scheduling and stores the window. If Scheduling is down, cold or slower than SCHEDULING_TIMEOUT_S, Trips returns 503 and leaves the trip unchanged (ADR-6, ADR-8), and the user has to press "Confirm dates" again. A queue would let Trips accept the confirmation at once and finish it when Scheduling is back.

**Decision:** I did not build it. Confirming dates stays synchronous: it either succeeds with the real window from Scheduling, or fails with a clear 503 and changes nothing. A message broker (Service Bus, RabbitMQ, Redis) and a background worker to drain it are out of scope for this assignment, and both would run all the time, against the scale-to-zero, pay-per-use deployment.

**Alternatives considered:** A Service Bus queue plus a worker that retries the confirmation (out of scope, a third running component, and a monthly cost). An outbox table in trips_db retried at the next request or startup (no broker, but the trip would sit in a "pending" state that the UI and the task board would have to show, and a retry could confirm a window that is no longer the best one because availability changed in the meantime). Caching the last windows from Scheduling inside Trips (would let Trips confirm stale dates without Scheduling knowing).

**Consequences:** The user sometimes sees "The scheduling service is unavailable right now" and has to retry, usually only after a cold start; with Scheduling waking in under a minute and Trips waiting 10 seconds, most confirmations succeed on the first or second try. In exchange there is never a half-confirmed trip, no extra infrastructure, and the data is always exactly what Scheduling computed at that moment.

**Worth building when:** confirming dates fails often enough that users notice (for example more than 5% of confirmations returning 503 in the request logs over a month), or Scheduling gets an always-on instance anyway (then the queue no longer breaks scale to zero), or confirming dates starts triggering other work, such as notifying every member, where waiting for one HTTP call is no longer acceptable.
