# Database Reference Guide

The current database structure is managed by Django migrations under
`backend/*/migrations/`.

## Files

- `schema.sql` documents the pre-Django tables retained as a legacy migration and audit
  source. It is not the current application schema.
- `backups/` contains private local database backups and is excluded from Git and the
  submission package.
- `data/` may contain private legacy exports and is also excluded.

The running application uses normalized Django tables such as `accounts_user`,
`scheduling_appointment`, and `records_treatmentrecord`. Normal patient, appointment,
and treatment changes must be made through the application rather than manual database
edits.

## Initial Setup

Create an empty MySQL database named `dental_clinic`, configure `backend/.env`, and run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
```

Do not run `schema.sql` for a fresh Django installation. Run the optional legacy importer
only when the old tables already contain records that must be retained:

```powershell
.\.venv\Scripts\python.exe backend\manage.py import_legacy_data
```

After setup, start the complete system from the project folder:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

The backend connects to MySQL and serves JSON under `http://127.0.0.1:8000/api/`. Vite runs the
Vue frontend separately on port `5173` and proxies `/api` requests to Django.
