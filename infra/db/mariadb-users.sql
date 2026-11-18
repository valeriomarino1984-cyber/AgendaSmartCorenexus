-- Database e utenti per SVILUPPO e CI (in produzione si creano da cPanel, vedi docs/07-deploy-netsons.md).
-- Esecuzione come root di MariaDB:  mariadb -uroot < infra/db/mariadb-users.sql
CREATE DATABASE IF NOT EXISTS agenda_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Utente delle migrazioni: tutti i privilegi, ma solo su questo database.
CREATE USER IF NOT EXISTS 'agenda_migr'@'%' IDENTIFIED BY 'migr_dev';
GRANT ALL PRIVILEGES ON agenda_test.* TO 'agenda_migr'@'%';

-- Utente dell'applicazione: solo lettura e scrittura dei dati, nessuna modifica allo schema.
CREATE USER IF NOT EXISTS 'agenda_app'@'%' IDENTIFIED BY 'app_dev';
GRANT SELECT, INSERT, UPDATE, DELETE ON agenda_test.* TO 'agenda_app'@'%';
