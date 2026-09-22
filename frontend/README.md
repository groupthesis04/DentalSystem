# Frontend Beginner Guide

The frontend is a Vue 3 application. Make frontend changes only in `src/` and the two CSS files
listed below. Vite reads those source files directly while you work.

## Where to Make Changes

| What you want to change              | File or folder                                 |
| ------------------------------------ | ---------------------------------------------- |
| Public website                       | `src/views/PublicHome.vue`                     |
| Admin dashboard shell                | `src/views/DoctorDashboard.vue`                |
| Patient dashboard                    | `src/views/PatientDashboard.vue`               |
| Patient management                   | `src/components/doctor/PatientManagement.vue`  |
| Appointments and clinic availability | `src/components/doctor/ScheduleManagement.vue` |
| Services, promos, and feedback       | `src/components/doctor/ContentManagement.vue`  |
| Shared header, sidebar, modal, icons | `src/components/`                              |
| Calls to the Django backend          | `src/services/api.js`                          |
| Form validation                      | `src/services/validation.js`                   |
| Dates, money, and display helpers    | `src/services/format.js`                       |
| Main website styles                  | `styles.css`                                   |
| Dashboard and dark-theme styles      | `src/dashboard-theme.css`                      |

## Simple Application Flow

1. `index.html` creates the empty `<div id="app">` browser container.
2. `src/main.js` starts Vue inside that container.
3. `src/App.vue` chooses the public, admin, or patient view from the URL.
4. A view uses small components for repeated interface elements.
5. `src/services/api.js` sends JSON requests to the Django backend.

The files in `src/components/` are necessary shared pieces. For example, both dashboards use
`PortalHeader.vue`, `PortalSidebar.vue`, and `NotificationMenu.vue`. Keeping each piece separate
prevents the same code from being copied into several pages.

## First-Time Setup

From the `frontend` folder:

```powershell
npm.cmd install
```

## Start the Frontend

Start Django from the project root first. Then, from the `frontend` folder:

```powershell
npm.cmd run dev
```

`install` is needed only the first time. `dev` starts the Vue frontend and refreshes the browser
whenever you save a Vue file. On this computer, open `http://127.0.0.1:5173`.

## Open on a Phone

1. Connect the computer and phone to the same Wi-Fi network.
2. Start the Django backend from the main project folder:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

3. In a second terminal, start Vue from the `frontend` folder:

```powershell
npm.cmd run dev
```

4. Find the computer's Wi-Fi IPv4 address by running `ipconfig` and looking under the active
   Wireless LAN adapter.
5. On the phone, open `http://COMPUTER-IP:5173`. For example, if the address is
   `192.168.68.115`, open `http://192.168.68.115:5173`.

If Windows asks whether Node.js may communicate through the firewall, allow it on **Private
networks**. The phone uses only port `5173`; Vite forwards API requests to the backend on port
`8000` automatically.

## Optional Local Test Accounts

Copy `.env.example` to `.env.development.local` and enter development-only test credentials to
show account shortcuts in the login modal. Restart Vite after changing the file. The local file
is ignored and must never be committed or included in a submission package. Keep password values
in double quotes when they contain `#`, because unquoted `#` begins an environment-file comment.

## Formatting

```powershell
npm.cmd run format
```

`format` is optional and makes the Vue source consistent and readable. The Django backend runs
separately on port `8000` and Vite forwards `/api` requests to it automatically.

## Automated SMS (Semaphore)

The SMS section uses the Django backend, not browser storage. A Semaphore account,
funded credits, and an approved sender name are needed for real delivery. Until
configured, the dashboard shows **Semaphore is not connected**.
The **SMS Credits Remaining** card uses Semaphore's live account balance through
the Django backend. The backend caches successful lookups for 60 seconds because
Semaphore limits account requests to two per minute. Missing credentials and
provider errors display an unavailable state; no placeholder credit value is used.

1. Add these settings to `backend/.env`, never the frontend environment file:

```dotenv
SMS_ENABLED=1
SMS_CLINIC_NAME=BORJA Dental Clinic
SEMAPHORE_API_KEY=your-private-api-key
SEMAPHORE_SENDER_NAME=your-approved-sender-name
```

2. From the project root, apply the migration and restart Django:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

3. Keep a **third terminal** running the SMS worker from the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py process_sms --loop
```

The worker checks every 30 seconds. Keep MySQL and the worker online. In production,
run it as a supervised background service with automatic restart. Closing the browser
does not stop server-side reminders.

Open **SMS > SMS Center** to enable or disable the six rules independently.
**SMS > Templates** contains saved template cards, a sample phone preview, and
message settings. Create or duplicate templates, edit their content, and choose
an immediate, 5-, 15-, 30-, or 60-minute send delay. New copies are inactive by
default. Only one template per automation can be active; activating another
replaces the previous selection without sending duplicate messages. Reset discards
unsaved settings. Inactive templates can be deleted from their card after a
confirmation. The template currently assigned to an automation is protected;
activate another template first if it needs to be removed. Template text and
settings are stored in the database.

**SMS > Message Logs** is a separate page with summary counts, recipient/phone
search, message type, status, source, and date filters. Select a row or its eye
button to see the full message and recorded delivery activity. Counts reflect
the current filters; active rules remain clinic-wide. Dates use Philippine time.
Choose 10, 25, or 50 rows per page.

Resend is available only for a confirmed failure while its notification is still
valid and Semaphore is connected. Confirming creates a separate attempt using
the current patient number, appointment details, and active template. The
original log is preserved, and repeated clicks cannot duplicate that attempt.
Expired, disabled, paid-off, changed-status, and uncertain notices cannot be resent.
Test-message retries preserve their original test number and content.

Test SMS sends a real message only to the number entered in its dialog and uses
credits. The phone preview uses sample data and does not send anything.

- Booking requests, approvals, walk-ins, next visits, and cancellations create
  queue entries using the active template's send delay. The next-visit booking wizard sends only after the date
  and time slot have been confirmed.
- Balance reminders start seven days after an unpaid balance is recorded, then
  repeat every seven days. Partial payments keep the schedule; full payment stops it.
  Existing unpaid balances start their seven-day clock on the first worker run.
- Switching a rule off suppresses unsent messages. Switching it back on affects
  future events, not old suppressed messages. Submitted SMS cannot be recalled.
- Unsent messages expire after 24 hours to avoid old notices after downtime.
  An uncertain provider response appears under **Pending**, with **Needs review**
  in the message details, and is not automatically resent. Check Semaphore's log
  before sending again.
- **Sent** means network acceptance, not confirmed handset delivery or that the
  patient read the SMS. **Delivered** requires an explicit delivery confirmation;
  no delivery status is simulated.

Keep patient mobile numbers current. Supported numbers are Philippine mobile
numbers such as `09XXXXXXXXX` or `+639XXXXXXXXX`.
See [Semaphore's API documentation](https://www.semaphore.co/docs).
