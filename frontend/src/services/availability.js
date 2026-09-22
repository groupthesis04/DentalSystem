import { localDateIso } from "./format.js";

function normalizedDoctor(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

export function futureOpenSlots(availability, doctor = "", now = new Date()) {
  const today = localDateIso(now);
  const currentTime = `${String(now.getHours()).padStart(2, "0")}:${String(
    now.getMinutes(),
  ).padStart(2, "0")}`;
  const doctorName = normalizedDoctor(doctor);

  return (Array.isArray(availability) ? availability : [])
    .filter((slot) => {
      if (!slot || slot.booked || !slot.date || !slot.time) return false;
      if (slot.date < today || (slot.date === today && slot.time <= currentTime)) return false;
      return !doctorName || normalizedDoctor(slot.doctor) === doctorName;
    })
    .sort((left, right) =>
      `${left.date} ${left.time}`.localeCompare(`${right.date} ${right.time}`),
    );
}

export function availableSlotDates(slots) {
  return [...new Set((Array.isArray(slots) ? slots : []).map((slot) => slot.date))].sort();
}
