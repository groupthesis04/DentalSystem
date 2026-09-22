# BORJA Dental Record Management and Appointment System

BORJA Dental is a Vue 3 and Django 5.2 application for clinic scheduling, patient
records, treatment history, services, promotions, notifications, and reporting. Django
uses session authentication, CSRF protection, role checks, and MySQL through the Django
ORM.

## Project Structure

```text
backend/                    Django project and application source
frontend/                   Vue 3 and Vite application
database/schema.sql         Legacy pre-Django schema for migration reference only
DJANGO_BACKEND_GUIDE.md     Backend architecture and operational guide
```

Django migration files under each backend application's `migrations/` folder define the
current database schema. Do not delete them.

## Requirements

- Python 3.12
- Node.js and npm
- MySQL 8 or a compatible MySQL server

## First-Time Backend Setup

Start MySQL and create an empty database named `dental_clinic`. From the project root,
run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Edit `backend/.env` with the local MySQL credentials and a private Django secret key.
Never commit that file. Then create the current schema:

```powershell
python backend\manage.py migrate
python backend\manage.py createsuperuser
```

`import_legacy_data` is only needed when upgrading an older installation whose legacy
tables already contain data:

```powershell
python backend\manage.py import_legacy_data
```

## Start the System

Terminal 1, from the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

Terminal 2:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Do not use the removed legacy command
`python backend/server.py`.

## Open on a Phone

Connect the phone and computer to the same private Wi-Fi network. Run `ipconfig`, find
the computer's Wi-Fi IPv4 address, and open `http://COMPUTER-IP:5173` on the phone. Allow
Python and Node.js through Windows Firewall on Private networks when prompted.

## Optional Local Test-Account Shortcuts

The login modal can display development-only account shortcuts. Copy
`frontend/.env.example` to `frontend/.env.development.local`, enter local test
credentials, and restart Vite. The local file is ignored and must not be included in a
submission or public repository.

## Validation

Run backend checks and tests from the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
$env:DRMS_TEST_SQLITE="1"
.\.venv\Scripts\python.exe backend\manage.py test
Remove-Item Env:DRMS_TEST_SQLITE
```

Run frontend formatting verification and a production build:

```powershell
cd frontend
npm.cmd run format:check
npm.cmd run build
```

## Submission Safety

Do not submit `.env`, `.env.development.local`, `.venv`, `node_modules`, `dist`, logs,
Python cache files, database backups, or exported production data. The tracked
`.env.example` files contain placeholders only.
