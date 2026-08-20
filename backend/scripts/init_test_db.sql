-- Runs once when the dev Postgres container's data volume is first created.
-- Sets up a second database for the test suite (kept separate from the dev
-- database so running tests never touches data you're poking at manually)
-- and enables pgvector in both.
CREATE DATABASE job_alert_test;

\c job_alert
CREATE EXTENSION IF NOT EXISTS vector;

\c job_alert_test
CREATE EXTENSION IF NOT EXISTS vector;
