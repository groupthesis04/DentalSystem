# BORJA Dental Django Backend

The backend now uses Django, Django ORM, Django sessions, CSRF protection, and the
existing MySQL `dental_clinic` database. The Vue/Vite frontend remains separate.

## First-time setup

Start MySQL and create an empty `dental_clinic` database. From the project root in
PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
python backend\manage.py migrate
python backend\manage.py createsuperuser
```

Edit `backend/.env` before migrating. Use `python backend\manage.py import_legacy_data`
only when upgrading an older installation with populated legacy tables. The import is
idempotent and does not create duplicate rows when repeated.

## Start the backend

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

For local desktop use, open the frontend at `http://127.0.0.1:5173`. To test from a
phone on the same Wi-Fi, start Vite with its configured `0.0.0.0` host and open the
computer's LAN address, for example `http://192.168.1.10:5173`.

## Run tests

The database account does not need permission to create a MySQL test database. Tests
therefore use a disposable in-memory SQLite database:

```powershell
$env:DRMS_TEST_SQLITE="1"
python backend\manage.py test tests
Remove-Item Env:DRMS_TEST_SQLITE
```

Normal application commands still use MySQL.

See `DJANGO_BACKEND_GUIDE.md` in the project root for the complete beginner guide.

## SMS worker

Optional Semaphore settings are listed in `.env.example`. Set the API key only in
`backend/.env`, enable `SMS_ENABLED=1`, and restart the backend and worker after
configuration changes. Apply migrations first, then run from the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py process_sms --loop
```

Without `--loop`, the command performs one bounded queue pass. Run only one loop
per deployment; a database lease also prevents overlapping passes. The worker
handles event SMS, seven-day balance reminders, and provider status polling
independently of the browser. Production needs an always-on supervised worker
with outbound HTTPS access to `api.semaphore.co`.

Doctor-only endpoints: `GET /api/sms`, `PATCH /api/sms/rules`,
`GET /api/sms/logs`, `GET/POST/PATCH /api/sms/templates`, and `POST /api/sms/test`. Writes require session authentication
and CSRF protection. `/api/messages` remains internal portal messaging.
No provider keys are returned through these APIs.

The SMS Center reads the live credit balance from Semaphore's `GET /api/v4/account`
endpoint. Successful lookups are cached for 60 seconds to stay below Semaphore's
two-account-requests-per-minute limit. When the key is missing or Semaphore cannot
be reached, the dashboard shows the balance as unavailable instead of inventing a
credit total.

Migration `0003_sms_template_library` preserves existing rule messages in the
template library. Each rule selects one template; creating or duplicating a
template leaves it inactive unless explicitly activated. The selected template's
body and delay are mirrored to the rule used by the worker. Delays affect newly
queued events, not already scheduled messages; explicit test messages remain
immediate. Disabling the active template also disables its rule and suppresses
its unsent queue entries.

Explicit HTTP 429 rejections are retried at most twice. Ambiguous send failures
are marked `unknown` and require checking Semaphore's logs, preventing automatic
duplicate texts and charges. Provider `sent` means network acceptance, not verified
handset delivery. See `frontend/README.md` for setup and automation behavior.
