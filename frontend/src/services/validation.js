const limits = {
  id: 64,
  patient_id: 64,
  appointment_id: 64,
  booking_token: 64,
  recipient_id: 64,
  name: 120,
  first_name: 80,
  middle_name: 80,
  last_name: 80,
  email: 254,
  phone: 24,
  phone_number: 24,
  mobile_number: 24,
  address: 300,
  nationality: 80,
  occupation: 120,
  notes: 1000,
  password: 128,
  service: 120,
  doctor: 120,
  dates: 340,
  time_in: 8,
  time_out: 8,
  interval: 3,
  message: 1000,
  body: 1000,
  tooth_numbers: 120,
  procedure: 120,
  diagnosis: 700,
  treatment: 700,
  prescription: 700,
  remarks: 1000,
  title: 120,
  description: 500,
  detail_tagline: 240,
  detail_items: 1600,
  detail_duration: 80,
  detail_audience: 80,
  detail_care_note: 100,
};

const multilineFields = new Set([
  "address",
  "notes",
  "message",
  "body",
  "description",
  "detail_items",
  "diagnosis",
  "prescription",
  "remarks",
]);
const sensitiveFields = new Set(["password", "profile_image"]);
const htmlTagPattern = /<\s*\/?\s*[A-Za-z][^>]*>/;
const emailPattern = /^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$/;
const phonePattern = /^[0-9+() .-]{7,24}$/;
const toothPattern = /^[0-9#,.\-\s/]{1,120}$/;

function fieldLabel(name) {
  return name.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function cleanText(name, rawValue) {
  let value = String(rawValue ?? "");
  if (limits[name] && value.length > limits[name]) {
    throw new Error(`${fieldLabel(name)} is too long.`);
  }
  if (value.includes("\0")) throw new Error("Null characters are not allowed.");
  if (sensitiveFields.has(name)) return value;

  value = value.normalize("NFKC");
  value = value.replace(
    multilineFields.has(name)
      ? /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g
      : /[\u0000-\u001F\u007F]/g,
    "",
  );
  value = multilineFields.has(name)
    ? value.replaceAll("\r\n", "\n").replaceAll("\r", "\n").trim()
    : value.replace(/\s+/g, " ").trim();
  if (name !== "_website" && htmlTagPattern.test(value)) {
    throw new Error(`HTML is not allowed in ${name.replaceAll("_", " ")}.`);
  }
  return value;
}

function validatePhone(name, value, required = false) {
  if (!value && !required) return;
  const digits = value.replace(/\D/g, "");
  if (!phonePattern.test(value) || digits.length < 7 || digits.length > 15) {
    throw new Error(`Enter a valid ${fieldLabel(name).toLowerCase()}.`);
  }
}

function validateDate(name, value) {
  if (!value) return;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) throw new Error(`Choose a valid ${fieldLabel(name).toLowerCase()}.`);
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    throw new Error(`Choose a valid ${fieldLabel(name).toLowerCase()}.`);
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (name === "birthdate" && date > today) {
    throw new Error("Birthdate cannot be in the future.");
  }
  if (name === "birthdate") {
    const oldest = new Date(today);
    oldest.setFullYear(oldest.getFullYear() - 130);
    if (date < oldest) throw new Error("Birthdate must be within the last 130 years.");
  }
  if (name === "treatment_date" && date > today) {
    throw new Error("Treatment date cannot be in the future.");
  }
  if (name === "date" && date < today) {
    throw new Error("Appointment date cannot be in the past.");
  }
}

export function validatedPayload(rawPayload, options = {}) {
  const payload = {};
  for (const [name, value] of Object.entries(rawPayload)) {
    payload[name] = typeof value === "string" ? cleanText(name, value) : value;
  }
  if (String(payload._website || "").trim()) {
    throw new Error("Unable to process this request.");
  }
  if (payload.email && !emailPattern.test(payload.email)) {
    throw new Error("Enter a valid email address.");
  }
  for (const name of ["name", "first_name", "middle_name", "last_name"]) {
    if (payload[name] && (!/\p{L}/u.test(payload[name]) || /\d/.test(payload[name]))) {
      throw new Error(`${fieldLabel(name)} must contain letters and cannot contain numbers.`);
    }
  }
  validatePhone("phone", payload.phone || "");
  validatePhone("phone_number", payload.phone_number || "");
  validatePhone("mobile_number", payload.mobile_number || "", options.mobileRequired);
  for (const name of ["birthdate", "date", "treatment_date", "next_visit"]) {
    validateDate(name, payload[name]);
  }
  if (payload.next_visit && payload.treatment_date && payload.next_visit < payload.treatment_date) {
    throw new Error("Next visit cannot be before the treatment date.");
  }
  if (payload.tooth_numbers) {
    const teeth = payload.tooth_numbers.match(/\d+/g)?.map(Number) || [];
    if (
      !toothPattern.test(payload.tooth_numbers) ||
      !teeth.length ||
      teeth.some((tooth) => tooth < 1 || tooth > 85)
    ) {
      throw new Error("Enter valid tooth numbers between 1 and 85.");
    }
  }
  if (payload.amount_charged !== undefined || payload.amount_paid !== undefined) {
    const charged = Number(payload.amount_charged || 0);
    const paid = Number(payload.amount_paid || 0);
    if (!Number.isFinite(charged) || !Number.isFinite(paid) || charged < 0 || paid < 0) {
      throw new Error("Charged and paid amounts must be valid non-negative numbers.");
    }
    if (paid > charged) throw new Error("Amount paid cannot exceed amount charged.");
  }
  if (options.registration) {
    const password = String(payload.password || "");
    if (
      password.length < 10 ||
      !/[a-z]/.test(password) ||
      !/[A-Z]/.test(password) ||
      !/\d/.test(password) ||
      !/[^A-Za-z0-9]/.test(password)
    ) {
      throw new Error(
        "Password must be at least 10 characters and include uppercase, lowercase, number, and symbol characters.",
      );
    }
  }
  return payload;
}

export async function imageToDataUrl(file) {
  if (!file) return "";
  if (file.size > 2_000_000) throw new Error("Profile image must be under 2 MB.");
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Unable to read the selected image."));
    reader.readAsDataURL(file);
  });
}
