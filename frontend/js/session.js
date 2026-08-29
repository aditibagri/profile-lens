const STORAGE_KEY = "profile-lens.session.v1";
const API_KEY_STORAGE = "profile-lens.api-key";
export const SESSION_EVENT = "profile-lens-session";

export function emptyForm() {
  return {
    liAt: "",
    jsessionid: "",
    userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "",
    liap: "",
    bcookie: "",
    lidc: "",
    liA: "",
  };
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.liAt || !parsed?.jsessionid) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function loadApiKey() {
  try {
    return sessionStorage.getItem(API_KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

export function saveApiKey(value) {
  try {
    if (value) sessionStorage.setItem(API_KEY_STORAGE, value);
    else sessionStorage.removeItem(API_KEY_STORAGE);
  } catch {
    /* ignore */
  }
}

export function parsePastedBlock(text) {
  const form = emptyForm();
  const lines = String(text || "").split(/\r?\n/);
  let found = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 1) continue;
    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim();
    if (key === "LINKEDIN_LI_AT") {
      form.liAt = value;
      found = true;
    } else if (key === "LINKEDIN_JSESSIONID") {
      form.jsessionid = value;
      found = true;
    } else if (key === "LINKEDIN_USER_AGENT") form.userAgent = value;
    else if (key === "LINKEDIN_LIAP") form.liap = value;
    else if (key === "LINKEDIN_BCOOKIE") form.bcookie = value;
    else if (key === "LINKEDIN_LIDC") form.lidc = value;
    else if (key === "LINKEDIN_LI_A") form.liA = value;
  }
  return found ? form : null;
}

export function toRequestSession(session) {
  if (!session?.liAt || !session?.jsessionid) return null;
  return {
    liAt: session.liAt,
    jsessionid: session.jsessionid,
    userAgent: session.userAgent || "",
    liap: session.liap || "",
    bcookie: session.bcookie || "",
    lidc: session.lidc || "",
    liA: session.liA || "",
  };
}
