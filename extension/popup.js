const COOKIE_KEYS = ["li_at", "JSESSIONID", "liap", "bcookie", "lidc", "li_a"];

const statusEl = document.getElementById("status");
const checksEl = document.getElementById("checks");
const previewEl = document.getElementById("preview");
const copyBtn = document.getElementById("copy");
const saveBtn = document.getElementById("save");

function envEscape(value) {
  return String(value).replace(/\n/g, "").trim();
}

async function readLinkedInCookies() {
  const queries = [
    chrome.cookies.getAll({ domain: "linkedin.com" }),
    chrome.cookies.getAll({ domain: ".linkedin.com" }),
    chrome.cookies.getAll({ url: "https://www.linkedin.com/" }),
  ];
  const batches = await Promise.all(queries);
  const byName = {};
  for (const list of batches) {
    for (const cookie of list || []) {
      if (cookie?.name && cookie.value) {
        byName[cookie.name] = cookie.value;
      }
    }
  }
  return byName;
}

function buildSessionPayload(cookies, userAgent) {
  return {
    liAt: envEscape(cookies.li_at || ""),
    jsessionid: envEscape(cookies.JSESSIONID || ""),
    userAgent: envEscape(userAgent || ""),
    liap: envEscape(cookies.liap || ""),
    bcookie: envEscape(cookies.bcookie || ""),
    lidc: envEscape(cookies.lidc || ""),
    liA: envEscape(cookies.li_a || ""),
  };
}

function mask(value) {
  const text = envEscape(value);
  if (text.length <= 10) return text ? "••••" : "";
  return `${text.slice(0, 4)}…${text.slice(-4)}`;
}

function injectSession(payload) {
  localStorage.setItem("profile-lens.session.v1", JSON.stringify(payload));
  window.dispatchEvent(new Event("profile-lens-session"));
}

async function refresh() {
  const cookies = await readLinkedInCookies();
  const userAgent = navigator.userAgent;
  const hasSession = Boolean(cookies.li_at && cookies.JSESSIONID);

  checksEl.hidden = false;
  checksEl.innerHTML = COOKIE_KEYS.map((name) => {
    const present = Boolean(cookies[name]);
    const required = name === "li_at" || name === "JSESSIONID";
    const label = required ? `${name} (required)` : `${name} (optional)`;
    return `<li class="${present ? "" : "missing"}">${present ? "✓" : "✗"} ${label}</li>`;
  }).join("");

  if (!hasSession) {
    statusEl.className = "status bad";
    statusEl.textContent = "Log into LinkedIn in this browser first.";
    copyBtn.disabled = true;
    saveBtn.disabled = true;
    previewEl.hidden = true;
    return;
  }

  const payload = buildSessionPayload(cookies, userAgent);
  statusEl.className = "status ok";
  statusEl.textContent = "LinkedIn session detected.";
  previewEl.hidden = false;
  previewEl.textContent = [
    `li_at ${mask(cookies.li_at)}`,
    `JSESSIONID ${mask(cookies.JSESSIONID)}`,
  ].join("\n");
  copyBtn.disabled = false;
  saveBtn.disabled = false;
  copyBtn.dataset.payload = JSON.stringify(payload);
}

saveBtn.addEventListener("click", async () => {
  const payload = JSON.parse(copyBtn.dataset.payload || "null");
  if (!payload) return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !/^https?:/.test(tab.url || "")) {
    statusEl.className = "status bad";
    statusEl.textContent = "Open your Profile Lens site, then click this icon on that tab.";
    return;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: injectSession,
      args: [payload],
    });
    saveBtn.textContent = "Saved on this site";
    statusEl.className = "status ok";
    statusEl.textContent = "Connected. You can close this popup and look up a profile.";
  } catch {
    statusEl.className = "status bad";
    statusEl.textContent = "Could not save here. Stay on the Profile Lens tab and try again.";
  }
});

copyBtn.addEventListener("click", async () => {
  const payload = JSON.parse(copyBtn.dataset.payload || "null");
  if (!payload) return;
  const block = [
    `LINKEDIN_LI_AT=${payload.liAt}`,
    `LINKEDIN_JSESSIONID=${payload.jsessionid}`,
    `LINKEDIN_USER_AGENT=${payload.userAgent}`,
  ].join("\n");
  await navigator.clipboard.writeText(block);
  copyBtn.textContent = "Copied — paste on the site";
  setTimeout(() => {
    copyBtn.textContent = "Copy session";
  }, 1600);
});

refresh().catch(() => {
  statusEl.className = "status bad";
  statusEl.textContent = "Could not read LinkedIn cookies.";
});
