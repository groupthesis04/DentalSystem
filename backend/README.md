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

## Railway production security

Before deploying the backend, set `DRMS_DEBUG=0`, a unique random
`DRMS_DJANGO_SECRET_KEY` of at least 50 characters, and `DRMS_ALLOWED_HOSTS` to
the backend's explicit public hostname. Set `DRMS_COOKIE_SECURE=1` as well. The
frontend's HTTPS origin is already trusted for CSRF in `settings.py`; add any
other frontend origins through `DRMS_CSRF_TRUSTED_ORIGINS`.

Doctor and patient accounts sign in with their password. Five failed password
attempts within 15 minutes lock that account for 15 minutes across devices. The
account lockout migration does not revoke existing sessions. The optional
`/django-admin/` entry point remains available only in local development.

The patient-management page can disable or re-enable a linked patient account.
Disabling it revokes active sessions while keeping the patient profile and clinic
history. New registrations do not record a privacy or SMS choice. Automated SMS
starts off until the patient chooses to receive it in their profile; older records
whose choice is unknown are also suppressed. The patient's SMS preference history
retains subsequent choices and withdrawals with their recorder and time. Opting
out suppresses queued messages; a message already being sent finishes before the
change is saved. Account > Security > Activity Log shows account,
patient, treatment, appointment cancellation, and accepted SMS events with
opaque user and record IDs. It does not store passwords, verification codes,
message bodies, or patient details.

Production refuses to start with a missing, short, or known placeholder secret
or a wildcard host. It redirects HTTP to HTTPS, marks session and CSRF cookies
Secure, and initially sends HSTS with a one-hour lifetime. Do not enable HSTS
subdomains or preload until every affected hostname has been verified on HTTPS.
Changing the secret signs out existing users, so rotate it during a planned
deployment and ask users to log in again. Never copy the secret into source,
frontend variables, logs, or support messages.

After setting the production variables, run `python manage.py check --deploy`
with the production environment. The initial HSTS configuration intentionally
leaves subdomains and preload disabled, so Django reports only those two
advisory warnings.

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
The same worker checks approved appointments within the next 24 hours and
creates doctor dashboard reminders. Those reminders do not send patient SMS and
still run when Semaphore sending is disabled. It also creates a doctor dashboard
alert on a recorded next visit's clinic-local due date; assigning that date
continues to use the existing patient SMS rule.

Doctor-only endpoints: `GET /api/sms`, `PATCH /api/sms/rules`,
`GET /api/sms/logs`, `GET/POST/PATCH /api/sms/templates`, and `POST /api/sms/test`. Writes require session authentication
and CSRF protection. `/api/messages` remains internal portal messaging.
No provider keys are returned through these APIs.

## Claiming a clinic-created patient record

Patient registration checks email reputation through Abstract before creating
an account or starting the existing Semaphore identity challenge. The Django
backend calls `https://emailreputation.abstractapi.com/v1` with the Email
Reputation API key. In `backend/.env`, use
`ABSTRACT_EMAIL_REPUTATION_API_KEY=your-key`. On Railway, add that same variable
under **Backend service → Variables → New Variable**, then deploy the backend
service with the updated code. Remove the former Email Validation key variable
after the new variable is set. Keep the real key only in the backend environment;
do not add it to Vue/Vite variables or browser code.

The frontend posts the address to `POST /api/email-validation` after the email
field loses focus, and `POST /api/register` independently enforces the same
check. Both endpoints return sanitized statuses; uncertain or catch-all results
are distinct from an explicitly invalid address. A missing key or provider
outage pauses new registration with a temporary error, while existing account
login is unaffected. The backend briefly caches results and rate-limits check
requests. This feature needs no migration or additional Python package.

Registration creates a new account immediately only when no clinic patient record
matches. An unlinked clinic record starts a five-minute SMS code challenge instead.
The code is sent directly through the existing Semaphore transport to the mobile
number already on that record. The registration phone is used only for matching;
it never sets the OTP destination. The submitted password and code are stored as
hashes until verification. A successful code creates the User and sets the existing
PatientProfile's `user_id` in one database transaction, preserving its ID and all
related records. OTPs do not enter the regular SmsMessage queue, which would retain
the plaintext message body. Challenges older than one day are purged by the SMS
worker and opportunistically on new registration requests.

Apply `accounts.0002_patientaccountverification` before enabling the new web code.
For local PowerShell development from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
$env:DRMS_TEST_SQLITE="1"
.\.venv\Scripts\python.exe backend\manage.py test tests.test_registration_linking
Remove-Item Env:DRMS_TEST_SQLITE
```

On Railway, keep `SMS_ENABLED=1`, `SMS_CLINIC_NAME=BORJA Dental Clinic`,
`SEMAPHORE_API_KEY` and `SEMAPHORE_SENDER_NAME` on the Django web service. Keep
the existing `DRMS_DB_*` and Django secret/host/cookie variables. In that service's
Settings, set the **Pre-deploy Command** to `python backend/manage.py migrate` if
its root directory is the repository root, or `python manage.py migrate` if its
root directory is `backend/`. This runs the migration before the new deployment
starts. From a linked repository root, `railway up --service YOUR_WEB_SERVICE`
deploys the web code and `railway up --service YOUR_FRONTEND_SERVICE` deploys the
Vue code if it runs as a separate Railway service. A Git-connected service can use
its existing push workflow. Deploy the migrated web service before updating the
SMS worker service. The regular SMS worker is still needed for appointment
automations, but account verification sends synchronously from Django.

To test real delivery, create a clinic patient with a mobile you control and no
linked account, then register with matching name, birthdate, email and mobile.
The API should return `verification_required` and a masked number. Check Semaphore's
message log for provider acceptance and enter the received code within five
minutes. Use the clinic's patient detail page or Django shell to record the
PatientProfile ID and counts of appointments/treatments before and after linking;
they must remain the same. Never copy a live OTP into logs or support messages.
For example, run this from the repository root before and after verification,
replacing `pat_...` with the clinic record's ID:

```powershell
.\.venv\Scripts\python.exe backend\manage.py shell -c "from accounts.models import PatientProfile; from scheduling.models import Appointment; from records.models import TreatmentRecord; p=PatientProfile.objects.get(pk='pat_...'); print({'id': p.id, 'user_id': p.user_id, 'appointments': Appointment.objects.filter(patient=p).count(), 'treatments': TreatmentRecord.objects.filter(patient=p).count()})"
```

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
