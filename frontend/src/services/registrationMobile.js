const LOCAL_MOBILE = /^9\d{9}$/;
const COMPLETE_MOBILE = /^(?:\+63|63|0)?(9\d{9})$/;

export const MOBILE_LENGTH_MESSAGE = "Enter a valid 10-digit Philippine mobile number.";
export const MOBILE_PREFIX_MESSAGE = "Philippine mobile numbers must begin with 9.";

// Only complete numbers are normalized here. Partial input is handled by the field.
export function localMobileFromPaste(value) {
  const compact = String(value ?? "")
    .trim()
    .replace(/\s+/g, "");
  return COMPLETE_MOBILE.exec(compact)?.[1] ?? null;
}

export function registrationMobileError(value) {
  const digits = String(value ?? "");
  if (digits && !digits.startsWith("9")) return MOBILE_PREFIX_MESSAGE;
  if (!LOCAL_MOBILE.test(digits)) return MOBILE_LENGTH_MESSAGE;
  return "";
}

export function internationalRegistrationMobile(value) {
  const error = registrationMobileError(value);
  if (error) throw new Error(error);
  return `+63${value}`;
}
