/** API client for the FastAPI backend (kept separate from Vue UI logic). */

export async function fetchUiConfig() {
  const res = await fetch("/ui/config");
  if (!res.ok) throw new Error("Could not load UI config.");
  return res.json();
}

export async function fetchProfile({ url, apiKey, adapter }) {
  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;

  const params = new URLSearchParams();
  if (adapter) params.set("adapter", adapter);
  const qs = params.toString();
  const endpoint = qs ? `/v1/profile?${qs}` : "/v1/profile";

  const res = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify({ url }),
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.error || body.detail || `Request failed (${res.status})`);
  }
  return body; // { adapter, data }
}

export async function listAdapters() {
  const res = await fetch("/v1/adapters");
  if (!res.ok) throw new Error("Could not load adapters.");
  return res.json();
}
