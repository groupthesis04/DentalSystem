# Dental Record Management System

This project uses a Python HTTP backend, a responsive HTML/CSS/JavaScript frontend, and MySQL persistence.

## Project layout

- `backend/core.py` - shared validation, security, and storage helpers
- `backend/routes/` - authentication, patient, appointment, availability, treatment, service, and messaging routes
- `public/` - application pages, scripts, styles, and browser assets
- `database/` - MySQL schema
- `tools/` - database migration utility
- `tests/` - security smoke tests
- `docs/` - project documentation and system flowchart
- `data/` - ignored JSON migration backup and optional JSON storage

## Requirements

- Python 3.11 or newer
- MySQL Server 8.x
- Python packages from `requirements.txt`

```powershell
python -m pip install -r requirements.txt
```

## MySQL setup

Run `database/schema.sql` from MySQL Workbench or the MySQL command line using an administrator account. Then create a restricted application account and grant it access to the clinic database.

```sql
CREATE USER 'dental_app'@'localhost' IDENTIFIED BY 'replace-with-a-strong-password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX
  ON dental_clinic.* TO 'dental_app'@'localhost';
FLUSH PRIVILEGES;
```

Copy `.env.example` to `.env`, then replace every placeholder secret. The server reads `.env` automatically.

```text
DRMS_STORAGE=mysql
DRMS_DB_HOST=127.0.0.1
DRMS_DB_PORT=3306
DRMS_DB_NAME=dental_clinic
DRMS_DB_USER=dental_app
DRMS_DB_PASSWORD=your-strong-database-password
DRMS_STAFF_CODE=your-long-random-staff-registration-code
```

`DRMS_DB_AUTO_INIT=1` creates missing tables when the database account has permission. Set it to `0` after running `database/schema.sql` if schema creation should be administrator-controlled.

## Existing data migration

To import the current JSON records into an empty MySQL database:

```powershell
python tools/migrate_json_to_mysql.py --source data/app_data.json
```

The migration refuses to replace existing clinic data. Use `--force` only after making a database backup and intentionally choosing replacement.

## Run

```powershell
python server.py --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The first doctor account can be created through Sign Up by selecting `Doctor / Staff` and entering the configured `DRMS_STAFF_CODE`.

Doctor accounts manage clinic schedules from **Appointments > Clinic availability**. An admin can select multiple dates in one month, set the dentist's time-in and time-out, and generate 15-, 30-, or 60-minute appointment slots in one batch. Pending requests leave a slot open; accepting one request closes that exact dentist, date, and time to patients and cancels competing pending requests. Cancelling the accepted appointment makes the slot available again.

For isolated migration or automated tests only, JSON storage remains available explicitly:

```powershell
python server.py --storage json --data-file data/test.json --port 8000
```

## Security controls

- Central server-side field allowlists, size limits, normalization, and validation
- Client-side native constraints and JavaScript verification
- PBKDF2 password hashing with per-password salts
- Session-bound CSRF tokens and strict same-site cookies
- Same-origin enforcement and restrictive browser security headers
- Endpoint-specific IP rate limiting with `429` and `Retry-After`
- Off-screen honeypots on all submitted forms
- Role checks for doctor-only and patient-only operations

Set `DRMS_COOKIE_SECURE=1` when the application is served over HTTPS. Keep `.env` out of source control and use a dedicated MySQL account rather than `root` in production.
