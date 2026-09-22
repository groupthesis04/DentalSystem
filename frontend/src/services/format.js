export function formatDate(value) {
  if (!value) return "-";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return year && month && day ? `${month}/${day}/${year}` : String(value);
}

export function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export function localDateIso(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function formatMoney(value) {
  const amount = Number(value || 0);
  return `PHP ${amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function initials(name, fallback = "U") {
  return (
    String(name || "")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("") || fallback
  );
}

export function calculateAge(birthdate) {
  if (!birthdate) return "";
  const born = new Date(`${birthdate}T00:00:00`);
  if (Number.isNaN(born.getTime())) return "";
  const today = new Date();
  let age = today.getFullYear() - born.getFullYear();
  const birthdayPassed =
    today.getMonth() > born.getMonth() ||
    (today.getMonth() === born.getMonth() && today.getDate() >= born.getDate());
  if (!birthdayPassed) age -= 1;
  return Math.max(age, 0);
}

export function treatmentProcedure(record) {
  return record?.procedure || record?.treatment || record?.diagnosis || "Treatment";
}

export function treatmentBalance(record) {
  if (record?.balance !== undefined && record?.balance !== null) {
    return Number(record.balance || 0);
  }
  return Number(record?.amount_charged || 0) - Number(record?.amount_paid || 0);
}

export function statusLabel(status) {
  const labels = {
    pending: "Pending",
    approved: "Accepted",
    accepted: "Accepted",
    completed: "Completed",
    cancelled: "Cancelled",
    paid: "Paid",
    unpaid: "Unpaid",
  };
  return labels[String(status || "").toLowerCase()] || String(status || "Unknown");
}

export function relativeTime(value) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp.getTime()) / 1000));
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return timestamp.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
