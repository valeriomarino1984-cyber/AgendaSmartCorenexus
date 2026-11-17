-- Ruoli PostgreSQL di CoreNexus Agenda. Da eseguire UNA volta per database, come superuser.
-- Variabili psql richieste: migrator_password, app_password, dbname
--   psql -v migrator_password=... -v app_password=... -v dbname=corenexus -f roles.sql
\set ON_ERROR_STOP on

-- Proprietario dello schema: usato solo dalle migrazioni Alembic.
CREATE ROLE corenexus_migrator LOGIN PASSWORD :'migrator_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

-- Ruolo dell'applicazione: non proprietario delle tabelle, quindi soggetto alla RLS.
CREATE ROLE corenexus_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

ALTER DATABASE :"dbname" OWNER TO corenexus_migrator;
ALTER SCHEMA public OWNER TO corenexus_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dbname" TO corenexus_app;
