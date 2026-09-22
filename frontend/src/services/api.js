import { reactive } from "vue";

export const session = reactive({
  user: null,
  csrfToken: "",
  checked: false,
});

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function fetchJson(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      "X-Requested-With": "DentalSystem",
      "Cache-Control": "no-cache",
      ...(options.headers || {}),
    },
  });

  const data = await response.json().catch(() => ({}));
  return { response, data };
}

export async function refreshCsrfToken() {
  let result;
  try {
    result = await fetchJson("/api/session", { method: "GET" });
  } catch {
    throw new Error("Cannot reach the server. Please try again.");
  }

  const { response, data } = result;
  if (!response.ok) {
    const error = new Error(data.error || "Could not initialize the security session.");
    error.status = response.status;
    error.data = data;
    throw error;
  }

  session.csrfToken = data.csrf_token || "";
  if (!session.csrfToken) {
    throw new Error("Could not initialize the security token. Refresh the page and try again.");
  }
  return session.csrfToken;
}

async function performApiRequest(path, options, method, hasBody) {
  const headers = {
    ...(hasBody ? { "Content-Type": "application/json" } : {}),
    ...(session.csrfToken && UNSAFE_METHODS.has(method)
      ? { "X-CSRFToken": session.csrfToken }
      : {}),
    ...(options.headers || {}),
  };

  return fetchJson(path, {
    method,
    headers,
    body: hasBody
      ? typeof options.body === "string"
        ? options.body
        : JSON.stringify(options.body)
      : undefined,
  });
}

export async function apiRequest(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const hasBody = options.body !== undefined && options.body !== null;

  // Always have a token before an unsafe request. This is especially important
  // after a deployment, browser restore, login/logout rotation, or stale tab.
  if (UNSAFE_METHODS.has(method) && !session.csrfToken) {
    await refreshCsrfToken();
  }

  let result;
  try {
    result = await performApiRequest(path, options, method, hasBody);
  } catch {
    throw new Error("Cannot reach the server. Please try again.");
  }

  // Django can rotate the CSRF secret after authentication. If the browser had
  // a stale token, obtain a fresh token once and retry the original write.
  const csrfRejected =
    result.response.status === 403 &&
    String(result.data?.error || "").toLowerCase().includes("security token");

  if (csrfRejected && UNSAFE_METHODS.has(method) && !options.__csrfRetried) {
    await refreshCsrfToken();
    return apiRequest(path, { ...options, __csrfRetried: true });
  }

  const { response, data } = result;
  if (data.csrf_token) session.csrfToken = data.csrf_token;

  if (!response.ok) {
    const error = new Error(data.error || "Something went wrong.");
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export async function refreshSession() {
  const data = await apiRequest("/api/session");
  session.user = data.user || null;
  session.csrfToken = data.csrf_token || "";
  session.checked = true;
  return session.user;
}

export async function signOut() {
  await apiRequest("/api/logout", { method: "POST", body: {} });
  session.user = null;
  // Logout can rotate/clear authentication state. Get a new anonymous CSRF token
  // the next time an unsafe request is made.
  session.csrfToken = "";
}
