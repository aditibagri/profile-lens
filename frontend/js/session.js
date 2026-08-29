const STORAGE_KEY = "profile-lens.session.v1";
const API_KEY_STORAGE = "profile-lens.api-key";
const SCHEMA_STORAGE = "profile-lens.response-schema.v3";
const ADAPTERS_STORAGE = "profile-lens.user-adapters.v1";
export const SESSION_EVENT = "profile-lens-session";
export const RESERVED_ADAPTERS = new Set(["profilelens", "custom"]);
export const ADAPTER_NAME = /^[a-z][a-z0-9_-]{0,31}$/;

export const FALLBACK_SCHEMA = [
  { to: "firstName", from: "firstName" },
  { to: "lastName", from: "lastName" },
  { to: "fullName", from: "fullName" },
  { to: "headline", from: "headline" },
  { to: "location", from: "location" },
  { to: "industry", from: "industry" },
  { to: "linkedinDescription", from: "about" },
  { to: "linkedinProfileUrl", from: "profileUrl" },
  { to: "linkedinProfileSlug", from: "publicId" },
  { to: "companyName", from: "$currentJob.company" },
  { to: "jobTitle", from: "$currentJob.title" },
  { to: "linkedinSchoolName", from: "$school.school" },
  { to: "linkedinSkillsLabel", from: "skills" },
  { to: "experienceJson", from: "experience" },
  { to: "educationJson", from: "education" },
];

export function cloneRows(rows) {
  return (rows || []).map((row) => ({
    to: String(row.to || ""),
    from: String(row.from || row.from_ || "fullName"),
  }));
}

export function rowsEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  return a.every((row, i) => row.to === b[i].to && row.from === b[i].from);
}

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

export function loadSchemaRows() {
  try {
    const raw = localStorage.getItem(SCHEMA_STORAGE);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.length) return null;
    return cloneRows(parsed);
  } catch {
    return null;
  }
}

export function saveSchemaRows(rows) {
  localStorage.setItem(SCHEMA_STORAGE, JSON.stringify(cloneRows(rows)));
}

export function loadUserAdapters() {
  try {
    const raw = localStorage.getItem(ADAPTERS_STORAGE);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((row) => row && ADAPTER_NAME.test(row.name) && row.template && typeof row.template === "object")
      .map((row) => ({
        name: row.name,
        description: String(row.description || "Your adapter"),
        template: row.template,
      }));
  } catch {
    return [];
  }
}

export function saveUserAdapters(adapters) {
  localStorage.setItem(ADAPTERS_STORAGE, JSON.stringify(adapters || []));
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
