# Initial Azure setup (to move into README)

Run in bash, not zsh.

## 1. Subscription and region
az login --tenant <IE University tenant ID>
az account set --subscription <Azure for Students subscription ID>
az policy assignment list --query "[].{policy:displayName, regions:parameters.listOfAllowedLocations.value}" -o json
Allowed regions: italynorth, francecentral, switzerlandnorth, norwayeast, germanywestcentral. Chosen: francecentral (closest to Madrid).

## 2. Providers
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do az provider register --namespace $p; done

## Variables
PREFIX=azapata-ieu2024
RG=rg-$PREFIX
LOCATION=francecentral
UI_STORAGE=azapataieu2024ui
SQL_SERVER=$PREFIX-sql

## 2b. Resource group
az group create --name $RG --location $LOCATION

## 3. UI: storage static website
az storage account create --name $UI_STORAGE --resource-group $RG --location $LOCATION --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2
az storage blob service-properties update --account-name $UI_STORAGE --static-website --index-document index.html
az storage account show --name $UI_STORAGE --resource-group $RG --query primaryEndpoints.web -o tsv
Public URL (the only CORS origin): https://azapataieu2024ui.z28.web.core.windows.net

## 4. SQL server and two serverless databases (free offer)
Passwords are generated locally and kept outside the repo (~/.tripsync-azure-secrets); they are never written in any file in the repository.
az sql server create --name $SQL_SERVER --resource-group $RG --location $LOCATION --admin-user tripsyncadmin --admin-password "<SQL_ADMIN_PASSWORD>"
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
az sql db create --resource-group $RG --server $SQL_SERVER --name $PREFIX-scheduling-db --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
az sql db create --resource-group $RG --server $SQL_SERVER --name $PREFIX-trips-db --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
Free offer: auto-pause fixed at 60 min and max size 32 GB; --auto-pause-delay and --max-size are not allowed.

Contained users (firewall opened to my IP only for this, then closed):
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER --name SetupFromMyLaptop --start-ip-address <my IP> --end-ip-address <my IP>
sqlcmd -S tcp:$SQL_SERVER.database.windows.net,1433 -U tripsyncadmin -P "<SQL_ADMIN_PASSWORD>" -d $PREFIX-scheduling-db -Q "CREATE USER scheduling_user WITH PASSWORD = '<SCHEDULING_DB_PASSWORD>'; ALTER ROLE db_ddladmin ADD MEMBER scheduling_user; ALTER ROLE db_datareader ADD MEMBER scheduling_user; ALTER ROLE db_datawriter ADD MEMBER scheduling_user;"
sqlcmd -S tcp:$SQL_SERVER.database.windows.net,1433 -U tripsyncadmin -P "<SQL_ADMIN_PASSWORD>" -d $PREFIX-trips-db -Q "CREATE USER trips_user WITH PASSWORD = '<TRIPS_DB_PASSWORD>'; ALTER ROLE db_ddladmin ADD MEMBER trips_user; ALTER ROLE db_datareader ADD MEMBER trips_user; ALTER ROLE db_datawriter ADD MEMBER trips_user;"
sqlcmd runs from the SQL Server Docker image: docker run --rm --platform linux/amd64 --entrypoint /opt/mssql-tools18/bin/sqlcmd mcr.microsoft.com/mssql/server:2022-latest ...
Isolation check: scheduling_user logs in to its own database; on the trips database it gets "Login failed" (evidence 07).
Connection check with the services' own driver: pymssql via services/scheduling/db.py connected as scheduling_user.
az sql server firewall-rule delete --resource-group $RG --server $SQL_SERVER --name SetupFromMyLaptop

## 6. Pipeline identity (OIDC, no stored Azure password)
az identity create --name $PREFIX-github --resource-group $RG --location $LOCATION
az role assignment create --assignee-object-id <identity principalId> --assignee-principal-type ServicePrincipal --role Contributor --scope <resource group id>
az identity federated-credential create --name github-main --identity-name $PREFIX-github --resource-group $RG --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange --subject "repo:${GH_REPO}:ref:refs/heads/main"
az identity federated-credential create --name github-main-ids --identity-name $PREFIX-github --resource-group $RG --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange --subject "repo:<owner>@<owner id>/<repo>@<repo id>:ref:refs/heads/main"
Run in bash: in zsh, "repo:$GH_REPO:ref" loses characters because :r is a zsh modifier.
Check: az identity federated-credential list --identity-name $PREFIX-github --resource-group $RG --query "[].subject" -o tsv

## 5. Container Apps (placeholder image until the first deploy)
az extension add --name containerapp --upgrade
az containerapp env create --name $PREFIX-env --resource-group $RG --location $LOCATION
(Creates a Log Analytics workspace automatically, used for container logs.)
az containerapp create --name $PREFIX-scheduling --resource-group $RG --environment $PREFIX-env --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8001 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --secrets database-url="mssql://scheduling_user:<password>@$SQL_SERVER.database.windows.net:1433/$PREFIX-scheduling-db" --env-vars DATABASE_URL=secretref:database-url ALLOWED_ORIGINS=<UI origin> PORT=8001
az containerapp create --name $PREFIX-trips --resource-group $RG --environment $PREFIX-env --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8002 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --secrets database-url="mssql://trips_user:<password>@$SQL_SERVER.database.windows.net:1433/$PREFIX-trips-db" --env-vars DATABASE_URL=secretref:database-url SCHEDULING_URL=https://<scheduling fqdn> SCHEDULING_TIMEOUT_S=10 ALLOWED_ORIGINS=<UI origin> PORT=8002
Ingress CORS stays off: CORS is done in the services' code. SCHEDULING_TIMEOUT_S is 10 on Azure so a cold Scheduling app has time to start.

## 7. GitHub secrets and variables
Secrets: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, SCHEDULING_DB_PASSWORD, TRIPS_DB_PASSWORD (gh secret set NAME --body ...)
Variables: PREFIX, RESOURCE_GROUP, UI_STORAGE (gh variable set NAME --body ...)

## 9. Read access for the professors
az role assignment create --assignee amartini@faculty.ie.edu --role Reader --scope <resource group id>
az role assignment create --assignee bserra@faculty.ie.edu --role Reader --scope <resource group id>