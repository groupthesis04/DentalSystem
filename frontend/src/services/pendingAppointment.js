export const PENDING_APPOINTMENT_KEY = "borja.pendingAppointment.v1";

const DRAFT_VERSION = 1;
const MAX_DRAFT_AGE_MS = 12 * 60 * 60 * 1000;
const BOOKING_TOKEN_PATTERN = /^booking_[A-Za-z0-9_-]{1,48}$/;

function draftStorage() {
  return globalThis.sessionStorage || null;
}

function cleanText(value, limit, multiline = false) {
  let text = String(value ?? "")
    .normalize("NFKC")
    .replace(/\0/g, "");
  text = multiline
    ? text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").trim()
    : text.replace(/\s+/g, " ").trim();
  return text.slice(0, limit);
}

function normalizeAppointment(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const appointment = {
    service: cleanText(value.service, 120),
    doctor: cleanText(value.doctor, 120),
    date: cleanText(value.date, 10),
    time: cleanText(value.time, 8),
    notes: cleanText(value.notes, 1000, true),
  };
  if (
    !appointment.service ||
    !appointment.doctor ||
    !/^\d{4}-\d{2}-\d{2}$/.test(appointment.date) ||
    !/^\d{2}:\d{2}$/.test(appointment.time)
  ) {
    return null;
  }
  return appointment;
}

function normalizeDraft(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const bookingToken = cleanText(value.bookingToken, 64);
  const createdAt = Number(value.createdAt);
  const updatedAt = Number(value.updatedAt);
  const appointment = normalizeAppointment(value.appointment);
  if (
    value.version !== DRAFT_VERSION ||
    !BOOKING_TOKEN_PATTERN.test(bookingToken) ||
    !Number.isFinite(createdAt) ||
    !Number.isFinite(updatedAt) ||
    Date.now() - createdAt > MAX_DRAFT_AGE_MS ||
    !appointment
  ) {
    return null;
  }
  return {
    version: DRAFT_VERSION,
    bookingToken,
    ownerUserId: cleanText(value.ownerUserId, 64),
    createdAt,
    updatedAt,
    appointment,
  };
}

function createBookingToken() {
  const randomPart = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID().replaceAll("-", "")
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 18)}`;
  return `booking_${randomPart.slice(0, 48)}`;
}

function writePendingAppointment(draft) {
  draftStorage()?.setItem(PENDING_APPOINTMENT_KEY, JSON.stringify(draft));
  return draft;
}

export function readPendingAppointment() {
  const storage = draftStorage();
  const stored = storage?.getItem(PENDING_APPOINTMENT_KEY);
  if (!stored) return null;
  try {
    const draft = normalizeDraft(JSON.parse(stored));
    if (draft) return draft;
  } catch {
    // Invalid browser data is discarded below.
  }
  storage.removeItem(PENDING_APPOINTMENT_KEY);
  return null;
}

export function pendingAppointmentForUser(userId = "") {
  const draft = readPendingAppointment();
  const normalizedUserId = cleanText(userId, 64);
  if (!draft) return null;
  if (draft.ownerUserId && draft.ownerUserId !== normalizedUserId) return null;
  return draft;
}

export function savePendingAppointment(appointment, { userId = "" } = {}) {
  const normalizedAppointment = normalizeAppointment(appointment);
  if (!normalizedAppointment) throw new Error("Complete the appointment details first.");

  const current = readPendingAppointment();
  const normalizedUserId = cleanText(userId, 64);
  if (current?.ownerUserId && current.ownerUserId !== normalizedUserId) {
    throw new Error(
      "This saved appointment belongs to a different patient account. Log in with that account to continue.",
    );
  }

  const now = Date.now();
  return writePendingAppointment({
    version: DRAFT_VERSION,
    bookingToken: current?.bookingToken || createBookingToken(),
    ownerUserId: current?.ownerUserId || normalizedUserId,
    createdAt: current?.createdAt || now,
    updatedAt: now,
    appointment: normalizedAppointment,
  });
}

export function claimPendingAppointment(userId) {
  const draft = readPendingAppointment();
  const normalizedUserId = cleanText(userId, 64);
  if (!draft) return { status: "none", draft: null };
  if (!normalizedUserId) return { status: "invalid-user", draft: null };
  if (draft.ownerUserId && draft.ownerUserId !== normalizedUserId) {
    return { status: "conflict", draft: null };
  }
  const claimed = { ...draft, ownerUserId: normalizedUserId, updatedAt: Date.now() };
  writePendingAppointment(claimed);
  return { status: "claimed", draft: claimed };
}

export function clearPendingAppointment(expectedToken = "") {
  const storage = draftStorage();
  const current = readPendingAppointment();
  if (!current) return true;
  if (expectedToken && current.bookingToken !== expectedToken) return false;
  storage?.removeItem(PENDING_APPOINTMENT_KEY);
  return true;
}
