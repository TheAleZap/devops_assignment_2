-- Idempotent local setup: one database and one login per service.
-- Run by sqlcmd with -v SCHEDULING_DB_PASSWORD=... -v TRIPS_DB_PASSWORD=...
-- Safe to run any number of times: every statement checks before it creates.

IF DB_ID('scheduling_db') IS NULL CREATE DATABASE scheduling_db;
GO
IF DB_ID('trips_db') IS NULL CREATE DATABASE trips_db;
GO

IF SUSER_ID('scheduling_user') IS NULL
    CREATE LOGIN scheduling_user WITH PASSWORD = '$(SCHEDULING_DB_PASSWORD)';
ELSE
    ALTER LOGIN scheduling_user WITH PASSWORD = '$(SCHEDULING_DB_PASSWORD)';
GO
IF SUSER_ID('trips_user') IS NULL
    CREATE LOGIN trips_user WITH PASSWORD = '$(TRIPS_DB_PASSWORD)';
ELSE
    ALTER LOGIN trips_user WITH PASSWORD = '$(TRIPS_DB_PASSWORD)';
GO

USE scheduling_db;
IF USER_ID('scheduling_user') IS NULL CREATE USER scheduling_user FOR LOGIN scheduling_user;
ALTER ROLE db_ddladmin ADD MEMBER scheduling_user;
ALTER ROLE db_datareader ADD MEMBER scheduling_user;
ALTER ROLE db_datawriter ADD MEMBER scheduling_user;
GO

USE trips_db;
IF USER_ID('trips_user') IS NULL CREATE USER trips_user FOR LOGIN trips_user;
ALTER ROLE db_ddladmin ADD MEMBER trips_user;
ALTER ROLE db_datareader ADD MEMBER trips_user;
ALTER ROLE db_datawriter ADD MEMBER trips_user;
GO
