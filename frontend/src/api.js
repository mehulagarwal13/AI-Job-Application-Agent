// Thin API client. The Vite dev server proxies /api/* to FastAPI (see vite.config.js).
// Auth: JWT bearer token, persisted in localStorage, attached to every request.

const TOKEN_KEY = "ajagent_token";

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = auth.getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...options, headers });
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (res.status === 401 && !path.startsWith("/auth/")) {
    auth.clear();
    onUnauthorized?.();
    throw new Error("Session expired — please log in again.");
  }
  if (!res.ok) {
    const detail = body?.detail || `Request failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export const api = {
  health: () => request("/health"),

  // Auth
  signup: (email, password) =>
    request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  login: (email, password) =>
    request("/auth/login", {
      method: "POST",
      // OAuth2 password flow: form-encoded, email travels as `username`
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    }),
  me: () => request("/auth/me"),

  // Resume pipeline
  listResumes: () => request("/resumes"),
  uploadResume: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/resumes/upload", { method: "POST", body: form });
  },
  extract: (resumeId) => request(`/resumes/${resumeId}/extract`, { method: "POST" }),
  parse: (resumeId) => request(`/resumes/${resumeId}/parse`, { method: "POST" }),
  embed: (resumeId) => request(`/resumes/${resumeId}/embed`, { method: "POST" }),

  // Jobs
  ingestJobs: ({ query, sources, country, location, results }) => {
    const params = new URLSearchParams({ query, sources, country, results });
    if (location) params.set("location", location);
    return request(`/jobs/ingest?${params}`, { method: "POST" });
  },
  embedPending: () => request("/jobs/embed-pending", { method: "POST" }),

  // Matching
  generateMatches: (resumeId, { location, minSalary } = {}) => {
    const params = new URLSearchParams();
    if (location) params.set("location_contains", location);
    if (minSalary) params.set("min_salary", minSalary);
    const qs = params.toString();
    return request(`/resumes/${resumeId}/matches/generate${qs ? `?${qs}` : ""}`, { method: "POST" });
  },
  listMatches: (resumeId, status) => {
    const qs = status ? `?status=${status}` : "";
    return request(`/resumes/${resumeId}/matches${qs}`);
  },
  setMatchStatus: (matchId, status) =>
    request(`/resumes/matches/${matchId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
};
