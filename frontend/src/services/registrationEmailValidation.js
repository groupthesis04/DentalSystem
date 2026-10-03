import { ref } from "vue";

export function normalizeRegistrationEmail(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .trim();
}

function normalizeResult(data, email) {
  const status = String(data?.status || "");
  const suggestion = normalizeRegistrationEmail(data?.suggested_email);
  const usableSuggestion = suggestion && suggestion !== email ? suggestion : "";
  if (status === "valid" && data?.valid === true) {
    return { valid: true, status: "valid", suggestion: usableSuggestion };
  }
  if (
    [
      "invalid",
      "disposable",
      "unknown",
      "service_unavailable",
      "already_registered",
      "rate_limited",
    ].includes(status)
  ) {
    return {
      valid: false,
      status,
      suggestion: ["invalid", "unknown"].includes(status) ? usableSuggestion : "",
    };
  }
  if (status === "suggestion") {
    return { valid: false, status, suggestion: usableSuggestion };
  }
  return { valid: false, status: "service_unavailable" };
}

export function createRegistrationEmailValidation({
  getEmail,
  isValidFormat,
  request,
  now = Date.now,
}) {
  const checking = ref(false);
  const status = ref("");
  const suggestedEmail = ref("");
  let checkedEmail = "";
  let checkedResult = null;
  let pendingEmail = "";
  let pendingEmailPromise = null;
  let requestVersion = 0;
  let rateLimitUntil = 0;

  function clear() {
    requestVersion += 1;
    checking.value = false;
    status.value = "";
    suggestedEmail.value = "";
    checkedEmail = "";
    checkedResult = null;
    pendingEmail = "";
    pendingEmailPromise = null;
  }

  function handleInput(event) {
    clear();
    const email = normalizeRegistrationEmail(event.target?.value);
    if (email && !isValidFormat(email)) status.value = "invalid_format";
  }

  function showResult(result) {
    checking.value = false;
    status.value = result.status;
    suggestedEmail.value = result.suggestion || "";
  }

  function check({ force = false } = {}) {
    const email = normalizeRegistrationEmail(getEmail());
    if (!isValidFormat(email)) {
      checking.value = false;
      status.value = email ? "invalid_format" : "";
      return Promise.resolve(false);
    }
    if (now() < rateLimitUntil) {
      checking.value = false;
      status.value = "rate_limited";
      return Promise.resolve(false);
    }
    if (!force && checkedEmail === email && checkedResult) {
      showResult(checkedResult);
      return Promise.resolve(checkedResult.valid);
    }
    if (pendingEmail === email && pendingEmailPromise) return pendingEmailPromise;

    const currentVersion = ++requestVersion;
    checking.value = true;
    status.value = "checking";
    suggestedEmail.value = "";
    const promise = request(email)
      .then((data) => normalizeResult(data, email))
      .catch((error) => {
        if (error?.status === 429) {
          const retryAfter = Number(error?.data?.retry_after);
          const waitSeconds =
            Number.isFinite(retryAfter) && retryAfter > 0 ? Math.min(retryAfter, 3600) : 60;
          return { valid: false, status: "rate_limited", retryUntil: now() + waitSeconds * 1000 };
        }
        return normalizeResult(error?.data, email);
      })
      .then((result) => {
        if (currentVersion !== requestVersion || normalizeRegistrationEmail(getEmail()) !== email) {
          return false;
        }
        if (result.status === "rate_limited") {
          rateLimitUntil = result.retryUntil || now() + 60_000;
          checkedEmail = "";
          checkedResult = null;
        } else {
          checkedEmail = email;
          checkedResult = result;
        }
        showResult(result);
        return result.valid;
      })
      .finally(() => {
        if (pendingEmailPromise === promise) {
          pendingEmail = "";
          pendingEmailPromise = null;
        }
      });
    pendingEmail = email;
    pendingEmailPromise = promise;
    return promise;
  }

  function dispose() {
    requestVersion += 1;
  }

  return { checking, status, suggestedEmail, clear, handleInput, check, dispose };
}
