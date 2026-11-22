# TripSync

### Less group-chat chaos. More trips that actually happen.

Planning a trip with friends should be the fun part—not a 200-message debate about dates, who's free, and who is booking the train. **TripSync brings the planning together:** everyone marks when they're available, the app finds the trip-length dates that work for the most people, and a shared task board makes it clear who's taking care of what.

**Pick dates. Rally the group. Split the to-dos. Go.**

> **Try the live app:** [Open TripSync](https://azapataieu2024ui.z28.web.core.windows.net)  
> The first request after a quiet period can take up to a minute: the containers scale to zero and the databases pause when idle (ADR-8). If you see **“Starting up, retrying”**, the app is waking up—give it a moment.

## In this README

- [What you can do](#what-you-can-do)
- [Architecture](#architecture-at-a-glance)
- [Run locally](#run-the-whole-system-locally)
- [Run one service](#run-a-single-service)
- [Tests and coverage](#tests-and-coverage)
- [Deployment](#how-deployment-works)
- [Initial Azure setup](#reproducing-the-initial-azure-setup)
- [API reference](#api)
- [Repository layout](#repository-layout)

## What you can do

- **Find a date that works:** friends submit their availability and TripSync ranks trip-length windows by how many people can make it.
- **Turn a date into a trip:** confirm the selected window and keep the trip details in one place.
- **Share the planning:** add members, create tasks, set priorities, and let people claim what they're handling.
- **Keep the group moving:** track task completion instead of losing booking decisions in the chat.

## Architecture at a glance

Two services, one per feature domain, each with its own SQL Server database, plus a static UI that calls both.

| Part | What it does | Local | Azure |
|---|---|---|---|
| **Scheduling** (`services/scheduling/`) | Date polls, each friend's free days, ranking of trip-length windows by attendance | port 8001 | Container App `azapata-ieu2024-scheduling` + database `azapata-ieu2024-scheduling-db` |
| **Trips** (`services/trips/`) | Trips, members, task board with priorities, confirming dates from a poll | port 8002 | Container App `azapata-ieu2024-trips` + database `azapata-ieu2024-trips-db` |
| **UI** (`ui/`) | Static HTML/CSS/JS that calls both services from the browser | nginx on port 8080 | Storage static website `azapataieu2024ui` |

`system.yaml` describes the whole system (env vars, ports, calls between services, Azure names), and each service has its OpenAPI document (`services/<name>/openapi.json`). CI checks that both match the code.

```mermaid
flowchart LR
    Browser["Browser<br/>ui/ (index.html, app.js, config.js)"]
    subgraph S["Scheduling service"]
        SR["router → service → repository"]
    end
    subgraph T["Trips service"]
        TR["router → service → repository"]
        TC["scheduling_client"]
    end
    SDB[("scheduling_db<br/>date_polls, availability")]
    TDB[("trips_db<br/>trips, members, tasks")]
    Browser -->|"HTTPS JSON (CORS: UI origin only)"| SR
    Browser -->|"HTTPS JSON (CORS: UI origin only)"| TR
    TR --> TC
    TC -->|"GET /api/scheduling/polls/{poll_id}/windows/{start}<br/>SCHEDULING_URL, 10 s timeout"| SR
    SR -->|scheduling_user| SDB
    TR -->|trips_user| TDB
```

**The service boundary:** confirming a trip's dates is the one flow that crosses it, server side. Trips asks Scheduling for the window and stores only the dates and the poll's ID (a plain integer, no foreign key across databases). If Scheduling is down or slow, confirming dates returns **503** with a clear message and the trip is left unchanged; everything else in Trips keeps working. An unknown poll returns 404, and a window outside the poll returns 400 (ADR-6, ADR-7).

### Databases (match `services/*/migrations/`)

```mermaid
erDiagram
    DATE_POLLS ||--o{ AVAILABILITY : has
    DATE_POLLS {
        INT id PK
        NVARCHAR title
        DATE range_start
        DATE range_end
        INT trip_length "CHECK >= 1"
        DATETIME2 created_at
    }
    AVAILABILITY {
        INT id PK
        INT date_poll_id FK "ON DELETE CASCADE"
        NVARCHAR participant "UNIQUE with poll and day"
        DATE day
    }
```

```mermaid
erDiagram
    TRIPS ||--o{ MEMBERS : has
    TRIPS ||--o{ TASKS : has
    MEMBERS |o--o{ TASKS : claims
    TRIPS {
        INT id PK
        NVARCHAR name
        NVARCHAR destination
        DATE start_date
        DATE end_date
        INT date_poll_id "poll in Scheduling, no FK"
        DATETIME2 created_at
    }
    MEMBERS {
        INT id PK
        INT trip_id FK "ON DELETE CASCADE"
        NVARCHAR name "UNIQUE per trip"
    }
    TASKS {
        INT id PK
        INT trip_id FK "ON DELETE CASCADE"
        NVARCHAR title
        INT claimed_by FK "NO ACTION"
        BIT done "default 0"
        NVARCHAR priority "002: low, normal, high; default normal"
    }
```

Each service also has a `schema_migrations` table with the migrations it has applied.

## Run the whole system locally

Needs Docker Desktop (on Apple Silicon, turn on Rosetta emulation for the SQL Server image).

```bash
git clone https://github.com/TheAleZap/devops_assignment_2.git
cd devops_assignment_2
cp .env.example .env        # then change the three passwords; .env is gitignored, never commit it
docker compose up --build
```

Open http://localhost:8080. API docs: http://localhost:8001/docs and http://localhost:8002/docs.

What happens: `sqlserver` starts, `db-init` runs `db/init.sql` once (one database and one login per service, safe to re-run), then each service applies its pending migrations at startup and serves on its port. The UI is served by a stock nginx image with `ui/config.local.js` mounted as `config.js`.

Stop with `docker compose stop`. Avoid `docker compose down -v` unless you want to delete the local data: `-v` removes the `sqlserver-data` volume.

## Run a single service

Trips has no `depends_on` on Scheduling, so it starts on its own:

```bash
docker compose up --build sqlserver db-init trips
```

Or outside Docker (Python 3.14), against the compose SQL Server:

```bash
docker compose up -d sqlserver db-init
python3 -m venv .venv && source .venv/bin/activate
cd services/trips
pip install -r requirements-dev.txt
set -a; source ../../.env; set +a
export DATABASE_URL="mssql://trips_user:$TRIPS_DB_PASSWORD@localhost:1433/trips_db"
python app.py
```

Same for Scheduling with `services/scheduling`, `scheduling_user`, `$SCHEDULING_DB_PASSWORD` and `scheduling_db`. Every setting is an environment variable with a default; `system.yaml` lists them all.

## Tests and coverage

The tests run against a real SQL Server and empty the tables before each test, so point them at a throwaway database, never at `trips_db` or `scheduling_db`:

```bash
docker compose up -d sqlserver
set -a; source .env; set +a
docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C \
  -Q "IF DB_ID('trips_test') IS NULL CREATE DATABASE trips_test; IF DB_ID('scheduling_test') IS NULL CREATE DATABASE scheduling_test"
cd services/trips        # with the venv active and requirements-dev.txt installed
DATABASE_URL="mssql://sa:$MSSQL_SA_PASSWORD@localhost:1433/trips_test" \
  python -m pytest --cov=trips --cov=db --cov=migrate --cov-report=term-missing --cov-fail-under=70
```

For Scheduling, run the same from `services/scheduling` with `scheduling_test` and `--cov=scheduling`. **Coverage in CI** (run 44907062326, the deploy of migration 002): **Scheduling 93.10%**, **Trips 95.95%**. CI fails a service below 70%.

The cross-seam integration test runs the whole system and also stops Scheduling to check the 503:

```bash
docker compose up -d --build
pip install -r tests/integration/requirements.txt
python -m pytest tests/integration -v
```

Lint: `ruff check .` from the repo root.

## How deployment works

Every change reaches `main` through a pull request, and every merge to `main` is deployed. Nothing is changed by hand on Azure after the initial setup.

```mermaid
flowchart LR
    Dev["Branch + pull request"] --> CI
    subgraph GH["GitHub Actions"]
        CI["ci.yml: lint, tests per service (coverage ≥ 70%),<br/>OpenAPI + system.yaml checks, integration test, image builds"]
        CD["cd.yml (push to main): CI, then deploy"]
    end
    CI -->|"merge to main"| CD
    CD -->|"push images tagged with the commit SHA"| GHCR[("GHCR<br/>ghcr.io/thealezap/tripsync-scheduling<br/>ghcr.io/thealezap/tripsync-trips")]
    CD -->|"OIDC as azapata-ieu2024-github"| AZ
    subgraph AZ["Azure: rg-azapata-ieu2024 (France Central)"]
        subgraph ENV["Container Apps environment azapata-ieu2024-env (Consumption, 0-1 replicas)"]
            CS["azapata-ieu2024-scheduling"]
            CT["azapata-ieu2024-trips"]
        end
        subgraph SQL["SQL server azapata-ieu2024-sql (serverless, free offer)"]
            DS[("azapata-ieu2024-scheduling-db")]
            DT[("azapata-ieu2024-trips-db")]
        end
        ST["Storage static website azapataieu2024ui"]
        LA["Log Analytics workspace (container logs)"]
    end
    GHCR -->|"image pull"| CS
    GHCR -->|"image pull"| CT
    CS --> DS
    CT --> DT
    CT -->|"HTTPS"| CS
```

- `ci.yml` runs on every push to a branch and on every pull request. Each service's tests run against a SQL Server container started in the job, with throwaway passwords generated for that run.

- `cd.yml` runs on every push to `main`: it reuses `ci.yml` (which on `main` also pushes the images to GHCR tagged with the commit SHA), then the deploy job signs in to Azure with OpenID Connect (no Azure password stored anywhere), stores each `DATABASE_URL` as a Container Apps secret from the GitHub secrets, points both Container Apps at the new images, generates `ui/config.js` with the services' HTTPS addresses and uploads `ui/` to the static website. It finishes with a health check that waits up to 6 minutes until both services report this commit's SHA on `/health`.

- Migrations are applied by each service at startup (`migrate.run()` in the lifespan). With at most one replica, two instances never race. Migrations are forward-only and expand-only, so the previous revision keeps working while the new one rolls out (see `services/trips/migrations/002_add_task_priority.sql`).

## Reproducing the initial Azure setup

Done once, by hand, before the first deploy. Run it in **bash** (in zsh, `"repo:$GH_REPO:ref"` loses characters, because `:r` is a zsh modifier). Passwords are generated locally and kept outside the repository; `<...>` marks values to fill in.

### 1. Subscription, region and providers

```bash
az login --tenant <IE University tenant ID>
az account set --subscription "Azure for Students"
az account show --query "{name:name, tenant:tenantId}" -o table     # check before changing anything
az policy assignment list --query "[].{policy:displayName, regions:parameters.listOfAllowedLocations.value}" -o json
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace $p
done
PREFIX=azapata-ieu2024
RG=rg-$PREFIX
LOCATION=francecentral          # allowed: italynorth, francecentral, switzerlandnorth, norwayeast, germanywestcentral
UI_STORAGE=azapataieu2024ui
SQL_SERVER=$PREFIX-sql
az group create --name $RG --location $LOCATION
```

### 2. UI: storage static website

```bash
az storage account create --name $UI_STORAGE --resource-group $RG --location $LOCATION \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2
az storage blob service-properties update --account-name $UI_STORAGE --static-website --index-document index.html
az storage account show --name $UI_STORAGE --resource-group $RG --query primaryEndpoints.web -o tsv
```

The printed URL is the public URL and the only CORS origin.

### 3. SQL server and two serverless databases (free offer)

```bash
az sql server create --name $SQL_SERVER --resource-group $RG --location $LOCATION \
  --admin-user tripsyncadmin --admin-password "<SQL_ADMIN_PASSWORD>"
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER --name AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
for db in scheduling trips; do
  az sql db create --resource-group $RG --server $SQL_SERVER --name $PREFIX-$db-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 \
    --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
done
```

The free offer fixes auto-pause at 60 minutes and the size at 32 GB.

### 4. One contained user per database

The firewall is opened to your IP only for this step. `sqlcmd` runs from the SQL Server image (`docker run --rm --platform linux/amd64 --entrypoint /opt/mssql-tools18/bin/sqlcmd mcr.microsoft.com/mssql/server:2022-latest ...`):

```bash
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER --name SetupFromMyLaptop \
  --start-ip-address <my IP> --end-ip-address <my IP>
sqlcmd -S tcp:$SQL_SERVER.database.windows.net,1433 -U tripsyncadmin -P "<SQL_ADMIN_PASSWORD>" -d $PREFIX-scheduling-db \
  -Q "CREATE USER scheduling_user WITH PASSWORD = '<SCHEDULING_DB_PASSWORD>'; ALTER ROLE db_ddladmin ADD MEMBER scheduling_user; ALTER ROLE db_datareader ADD MEMBER scheduling_user; ALTER ROLE db_datawriter ADD MEMBER scheduling_user;"
sqlcmd -S tcp:$SQL_SERVER.database.windows.net,1433 -U tripsyncadmin -P "<SQL_ADMIN_PASSWORD>" -d $PREFIX-trips-db \
  -Q "CREATE USER trips_user WITH PASSWORD = '<TRIPS_DB_PASSWORD>'; ALTER ROLE db_ddladmin ADD MEMBER trips_user; ALTER ROLE db_datareader ADD MEMBER trips_user; ALTER ROLE db_datawriter ADD MEMBER trips_user;"
az sql server firewall-rule delete --resource-group $RG --server $SQL_SERVER --name SetupFromMyLaptop
```

A contained user exists only in its own database, so `scheduling_user` gets "Login failed" on the Trips database (evidence `07-azure-db-isolation.png`).

### 5. Container Apps (with a placeholder image until the first deploy)

```bash
az extension add --name containerapp --upgrade
az containerapp env create --name $PREFIX-env --resource-group $RG --location $LOCATION
az containerapp create --name $PREFIX-scheduling --resource-group $RG --environment $PREFIX-env \
  --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8001 \
  --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
  --secrets database-url="mssql://scheduling_user:<password>@$SQL_SERVER.database.windows.net:1433/$PREFIX-scheduling-db" \
  --env-vars DATABASE_URL=secretref:database-url ALLOWED_ORIGINS=<UI origin> PORT=8001
az containerapp create --name $PREFIX-trips --resource-group $RG --environment $PREFIX-env \
  --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8002 \
  --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
  --secrets database-url="mssql://trips_user:<password>@$SQL_SERVER.database.windows.net:1433/$PREFIX-trips-db" \
  --env-vars DATABASE_URL=secretref:database-url SCHEDULING_URL=https://<scheduling address> SCHEDULING_TIMEOUT_S=10 ALLOWED_ORIGINS=<UI origin> PORT=8002
```

The environment creates a Log Analytics workspace, used for the container logs. Ingress CORS stays off because CORS is handled in the services' code. `SCHEDULING_TIMEOUT_S` is 10 on Azure so that a cold Scheduling has time to start.

### 6. Pipeline identity (OIDC, no stored Azure password)

```bash
GH_REPO=TheAleZap/devops_assignment_2
az identity create --name $PREFIX-github --resource-group $RG --location $LOCATION
az role assignment create --assignee-object-id <identity principalId> --assignee-principal-type ServicePrincipal \
  --role Contributor --scope <resource group id>
az identity federated-credential create --name github-main --identity-name $PREFIX-github --resource-group $RG \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "repo:${GH_REPO}:ref:refs/heads/main"
az identity federated-credential create --name github-main-ids --identity-name $PREFIX-github --resource-group $RG \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "repo:<owner>@<owner id>/<repo>@<repo id>:ref:refs/heads/main"
az identity federated-credential list --identity-name $PREFIX-github --resource-group $RG --query "[].subject" -o tsv
```

The identity is trusted only for runs on `main` of this repository, and is Contributor on this resource group only. The second credential covers GitHub's subject format with immutable owner and repository IDs.

### 7. GitHub secrets and variables

```bash
gh secret set AZURE_CLIENT_ID --body "<identity clientId>"
gh secret set AZURE_TENANT_ID --body "<tenant id>"
gh secret set AZURE_SUBSCRIPTION_ID --body "<subscription id>"
gh secret set SCHEDULING_DB_PASSWORD     # prompts, so the password is not in the shell history
gh secret set TRIPS_DB_PASSWORD
gh variable set PREFIX --body azapata-ieu2024
gh variable set RESOURCE_GROUP --body rg-azapata-ieu2024
gh variable set UI_STORAGE --body azapataieu2024ui
```

After the first push to `main`, set both GHCR packages (`tripsync-scheduling`, `tripsync-trips`) to **Public** in GitHub → Packages → Package settings, so Container Apps can pull them without registry credentials (ADR-8).

### 8. Read access for grading

```bash
az role assignment create --assignee amartini@faculty.ie.edu --role Reader --scope <resource group id>
az role assignment create --assignee bserra@faculty.ie.edu --role Reader --scope <resource group id>
```

From here on, every merge to `main` deploys.

## API

| Service | Method | Endpoint | Purpose |
|---|---|---|---|
| both | GET | `/health` | Status, database check and the deployed version (commit SHA) |
| Scheduling | POST | `/api/scheduling/polls` | Create a date poll |
| Scheduling | GET | `/api/scheduling/polls/{poll_id}` | A poll with everyone's availability |
| Scheduling | PUT | `/api/scheduling/polls/{poll_id}/availability` | Replace one participant's free days |
| Scheduling | GET | `/api/scheduling/polls/{poll_id}/best-windows` | Ranked date windows |
| Scheduling | GET | `/api/scheduling/polls/{poll_id}/windows/{start}` | One window (called by Trips across the seam) |
| Trips | POST | `/api/trips` | Create a trip, optionally with members |
| Trips | GET | `/api/trips/{trip_id}` | A trip with members, tasks and progress |
| Trips | POST | `/api/trips/{trip_id}/members` | Add a member |
| Trips | POST | `/api/trips/{trip_id}/tasks` | Add a task, with priority `low`, `normal` (default) or `high` |
| Trips | PUT | `/api/trips/{trip_id}/tasks/{task_id}/priority` | Change a task's priority |
| Trips | POST | `/api/trips/{trip_id}/tasks/{task_id}/claim` | A member claims a task |
| Trips | POST | `/api/trips/{trip_id}/tasks/{task_id}/complete` | Mark a claimed task done |
| Trips | PUT | `/api/trips/{trip_id}/dates` | Confirm the trip's dates from a poll window (calls Scheduling) |

Full request and response shapes: `services/scheduling/openapi.json` and `services/trips/openapi.json`.

## Repository layout

```
services/scheduling/, services/trips/   each: app.py, config.py, db.py, migrate.py, migrations/,
                                        <domain>/ (router, service, repository), tests/, Dockerfile,
                                        requirements.txt (direct), requirements.lock (pinned), openapi.json
ui/                                     static UI; config.local.js locally, config.js generated on deploy
db/init.sql                             local databases and logins (run by the db-init compose service)
docker-compose.yml, .env.example        the whole system locally
tests/integration/                      cross-seam tests against the running system
.github/workflows/                      ci.yml, cd.yml
system.yaml, system.schema.json         system description and its schema
scripts/check_system_yaml.py            checks system.yaml against the code
docs/assignment_2/evidence/             screenshots used in the report
ADR.md, AI_USAGE.md                     decisions and the AI log
```
