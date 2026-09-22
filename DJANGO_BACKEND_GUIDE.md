# BORJA Dental Clinic Django Backend Guide

This guide explains the converted backend in simple terms. The Vue pages, custom CSS,
Lucide icons, and Vite build remain the frontend of the system.

## 1. Backend Before the Conversion

The old backend used Python's `ThreadingHTTPServer` and `BaseHTTPRequestHandler`.
It manually matched URL paths, read JSON requests, created session tokens, checked CSRF
tokens, and used `mysql-connector-python` to copy whole collections into MySQL.

That approach worked for a small local project, but every web feature had to be written
and maintained manually.

## 2. Why ThreadingHTTPServer Was Removed

`ThreadingHTTPServer` is a basic HTTP server, not a complete web framework. It does not
provide models, migrations, an ORM, authentication, sessions, CSRF middleware, an admin
site, or a standard URL-routing system. Django provides these features in a consistent,
well-tested structure.

The old `server.py`, `core.py`, `mysql_store.py`, and custom `routes/` modules are no
longer part of the running backend.

## 3. What Django Does Now

Django now:

- receives every `/api/...` request;
- authenticates users and stores sessions;
- checks CSRF tokens on write requests;
- checks patient and doctor permissions;
- validates appointment, treatment, and profile data;
- reads and writes MySQL through Django ORM;
- creates notifications;
- provides analytics totals;
- provides an optional Django Admin site at `/django-admin/`.

Django Admin is an extra developer tool. It does not replace the Vue doctor dashboard.
Create a separate development administrator when Django Admin access is needed:

```powershell
python backend\manage.py createsuperuser
```

Then open `http://127.0.0.1:8000/django-admin/`.

## 4. How Vue Communicates With Django

Vue uses native `fetch()` through `frontend/src/services/api.js`.

During development, the browser opens Vite on port `5173`. A request such as
`/api/appointments` is sent to Vite, and Vite proxies it to Django on port `8000`.
The browser therefore sees one origin and no extra CORS package is required.

The normal data path is:

```text
Vue component -> apiRequest() -> Vite proxy -> Django view -> Django ORM -> MySQL
```

Django returns JSON, and Vue updates the existing interface with that JSON.

## 5. How Django Communicates With MySQL

`backend/dental_backend/settings.py` reads the existing `DRMS_DB_*` values from
`backend/.env`. The database engine is `django.db.backends.mysql`, which uses the
`mysqlclient` driver.

Credentials stay in `backend/.env`, which is ignored by Git. They are never placed in
Vue files.

## 6. Project Structure

```text
DentalSystemNew/
|-- backend/
|   |-- manage.py
|   |-- requirements.txt
|   |-- dental_backend/       settings, root URLs, WSGI, ASGI, shared API helpers
|   |-- accounts/             users, patient profiles, login, registration, patients
|   |-- scheduling/           appointments and dentist availability
|   |-- records/              treatment and payment records
|   |-- clinic/               services, promotions, and feedback
|   |-- communications/       notifications and patient/doctor messages
|   `-- tests/                Django API tests
|-- frontend/                 existing Vue 3 and Vite application
|-- database/                 legacy schema reference; private backups stay ignored
`-- DJANGO_BACKEND_GUIDE.md
```

Each Django app follows the same beginner-friendly pattern:

- `models.py` defines database structures.
- `views.py` handles requests and business rules.
- `urls.py` connects URL paths to views.
- `admin.py` registers useful models in Django Admin.
- `migrations/` records database structure changes.
- `apps.py` identifies the Django application.

## 7. Main Django Apps

### accounts

Handles `User`, `PatientProfile`, registration, login, logout, profile editing, and the
doctor's patient list. Email is the login name. Roles are `patient` and `doctor`.

### scheduling

Handles `Appointment` and `AvailabilitySlot`. It validates services, dates, times,
duplicate requests, approved-slot conflicts, cancellations, follow-ups, and manual
walk-in appointments.

### records

Handles `TreatmentRecord`. It calculates balance on the server and marks the related
appointment completed only when the treatment record is saved.

### clinic

Handles `Service`, `Promotion`, and `Feedback` content used by public pages and the
doctor dashboard.

### communications

Handles `Notification` and `Message`. Patients only receive their own notifications
and messages. Messages must be between a patient and clinic staff.

## 8. Main Models

- `User`: login account, password hash, role, name, phone, and profile image.
- `PatientProfile`: patient details and optional link to a login account.
- `Appointment`: patient, dentist, service, date, time, status, source, and notes.
- `AvailabilitySlot`: clinic-approved dentist date and time.
- `TreatmentRecord`: diagnosis, procedure, tooth numbers, amounts, prescription,
  remarks, and next-visit date.
- `Service`: clinic treatment offered to patients.
- `Promotion`: public clinic offer.
- `Feedback`: visitor or patient feedback.
- `Notification`: account alert connected to an appointment or treatment when useful.
- `Message`: patient-to-doctor or doctor-to-patient message.

## 9. Main API Endpoints

| Endpoint | Methods | Purpose |
| --- | --- | --- |
| `/api/session` | GET | Current user and CSRF token |
| `/api/register` | POST | Create and log in a patient account |
| `/api/login` | POST | Log in |
| `/api/logout` | POST | End the Django session |
| `/api/profile` | PATCH | Update the logged-in account |
| `/api/patients` | GET, POST, PATCH, DELETE | Doctor patient management |
| `/api/appointments` | GET, POST, PATCH, DELETE | Booking and status management |
| `/api/availability` | GET, POST, PATCH, DELETE | Dentist schedule management |
| `/api/records` | GET, POST, PATCH, DELETE | Treatment records |
| `/api/services` | GET, POST, PATCH, DELETE | Clinic services |
| `/api/promos` | GET, POST, PATCH, DELETE | Promotions |
| `/api/feedback` | GET, POST, PATCH, DELETE | Feedback |
| `/api/notifications` | GET, PATCH | List and mark notifications read |
| `/api/messages` | GET, POST | Patient/doctor messages |
| `/api/reports` | GET | Doctor analytics totals |
| `/api/health` | GET | Django and MySQL health check |

GET services, promos, feedback, and available slots are public. Private endpoints check
the Django session and the user's role.

## 10. Authentication Flow

1. Vue requests `/api/session` and receives a CSRF token.
2. The user submits login or registration.
3. Vue sends JSON and the `X-CSRFToken` header.
4. Django validates the credentials.
5. Django creates a server-side session and sends an HttpOnly session cookie.
6. Later requests include that cookie automatically.
7. Django loads `request.user` from the session.

New passwords use Django's password hashing. Existing accounts keep working: when an old
PBKDF2 password is entered successfully, the login view immediately replaces it with a
normal Django password hash. Plain-text passwords are never stored.

## 11. Appointment Flow

For a guest booking, the existing Vue frontend first stores the draft locally. It asks
the guest to log in or create an account. After authentication, Vue restores the draft
and shows the confirmation page.

When the authenticated patient confirms:

1. Django checks that the service still exists.
2. Django checks that the dentist and availability slot still exist.
3. Django checks the slot again inside a database transaction.
4. Django rejects duplicate active requests.
5. Django uses the booking token to prevent refresh duplicates.
6. Django saves the appointment as `pending`.
7. Django creates patient and doctor notifications.

The doctor can accept or cancel requests. Accepting one request cancels competing pending
requests for the same slot. Patients can cancel only their own appointments.

## 12. Treatment-Record Flow

The doctor selects `Completed` in the schedule. Vue opens the treatment-record form.
Django requires the diagnosis, clinic service, treatment date, and valid payment values.

Inside one database transaction Django:

1. saves the treatment record;
2. calculates `balance = amount charged - amount paid`;
3. sets the payment status;
4. marks the linked appointment `completed`;
5. creates notifications.

A direct status change to `completed` is rejected when no treatment record exists. If a
next-visit date is entered, the existing follow-up dialog lets the doctor choose a real
available slot and creates another appointment.

## 13. Notification Flow

Appointment and treatment actions call the small functions in
`communications/services.py`. Each notification has a recipient, type, title, message,
optional related entity, read flag, and timestamp. `/api/notifications` filters by the
logged-in user, so one patient cannot read another patient's alerts.

## 14. Existing Database Conversion

No database was dropped or reset. A verified private SQL backup was created in the
ignored `database/backups/` folder before migrations ran. Backups are not included in
the clean submission copy.

The old tables remain in MySQL as a migration/audit source. The running application uses
the normalized Django tables, including:

```text
accounts_user
accounts_patientprofile
scheduling_appointment
scheduling_availabilityslot
records_treatmentrecord
clinic_service
clinic_promotion
clinic_feedback
communications_notification
communications_message
```

Run this safe import after migrations:

```powershell
python backend\manage.py import_legacy_data
```

It preserves IDs and skips rows already imported. A second run adds zero duplicates.

## 15. CSRF in This Project

CSRF protects requests that change data. `/api/session` creates a Django CSRF token.
`apiRequest()` stores it and sends it as `X-CSRFToken` on POST, PATCH, and DELETE.
Django's `CsrfViewMiddleware` verifies the token. The project does not use
`@csrf_exempt` on normal API views.

The Vite proxy keeps browser requests same-origin during development. If direct
cross-origin access is introduced later, add the exact frontend origins to
`DRMS_CSRF_TRUSTED_ORIGINS` instead of disabling CSRF.

## 16. Sessions in This Project

Django stores session information in the `django_session` table. The browser receives an
HttpOnly `drms_session` cookie, so JavaScript cannot read its value. The cookie uses
`SameSite=Strict`. Set `DRMS_COOKIE_SECURE=1` only when the site is served over HTTPS.

The API always filters patient-owned appointments and treatment records by the profile
linked to `request.user`.

## 17. First-Time Installation

Start MySQL first, then run these commands from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\manage.py migrate
python backend\manage.py import_legacy_data
```

Copy `backend/.env.example` to `backend/.env` only when a local `.env` does not already
exist. Never overwrite working database credentials.

## 18. Start the Backend

Start MySQL in XAMPP or Windows Services. Then, from the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\manage.py runserver 0.0.0.0:8000
```

Health check: `http://127.0.0.1:8000/api/health`

## 19. Start the Frontend

In a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` on the computer. For a phone on the same Wi-Fi, open
`http://COMPUTER-LAN-IP:5173`. Vite already listens on `0.0.0.0` and proxies API calls
to Django.

## 20. Tests

The normal app uses MySQL. Automated tests use a disposable in-memory SQLite database so
the restricted MySQL account does not need permission to create `test_dental_clinic`.

```powershell
$env:DRMS_TEST_SQLITE="1"
python backend\manage.py test tests.test_django_api
Remove-Item Env:DRMS_TEST_SQLITE
```

Build the frontend with:

```powershell
cd frontend
npm run build
```

## 21. Common Errors and Simple Fixes

### Port 8000 is already in use

Close the older Python backend terminal. Find the process with:

```powershell
netstat -ano | Select-String ":8000"
```

Then stop only the known obsolete process, or start Django temporarily on another port.

### Port 5173 is already in use

Vite is already running in another terminal. Use that window or stop it before running
`npm run dev` again.

### MySQL connection error

Confirm that MySQL is running and that `DRMS_DB_HOST`, `DRMS_DB_PORT`, `DRMS_DB_NAME`,
`DRMS_DB_USER`, and `DRMS_DB_PASSWORD` in `backend/.env` are correct.

### CSRF verification failed

Refresh the page so `/api/session` supplies a new token. Confirm the frontend sends
`X-CSRFToken` and uses the Vite proxy. For a direct frontend origin, configure
`DRMS_CSRF_TRUSTED_ORIGINS`.

### `ModuleNotFoundError: django`

Activate `.venv` or run the interpreter directly:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
```

### Migration conflict

Do not delete tables or migration rows. Restore the verified backup if necessary and
inspect `python backend\manage.py showmigrations` before making changes.

## 22. Deployment Settings to Change Manually

The current setup is suitable for local development. Before deployment:

- create a long random `DRMS_DJANGO_SECRET_KEY`;
- set `DRMS_DEBUG=0`;
- set `DRMS_ALLOWED_HOSTS` to the real hostname;
- use HTTPS and set `DRMS_COOKIE_SECURE=1`;
- use a least-privilege MySQL account;
- configure backups and a production WSGI/ASGI server;
- run Django's deployment check.

Example:

```powershell
python backend\manage.py check --deploy
```

Private study questions and a code-review list are kept separately in
`DEFENSE_NOTES.md`; they are not required to install or run the application.
