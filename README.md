# LinkedIn Profile API

Hosted API that accepts a LinkedIn profile URL and returns the fields visible on the profile page as structured JSON.

This is a hiring-challenge submission: reverse-engineer the APIs LinkedIn's own website uses (Voyager), wrap them in a stable public API, and keep credentials out of source control.

## Setup

### 1. How to proceed — connect LinkedIn

Visitors on the hosted site do **not** edit `.env`. They open the homepage, connect once in the browser, then paste a profile URL.

Do **not** type a LinkedIn password into this app. Cookies expire; if lookups fail, connect again.

**On the live site**

1. Open the deployed URL.
2. Click **Connect**.
3. Either:
   - **Browser extension:** log into LinkedIn, stay on the Profile Lens tab, click the toolbar icon, then **Save to this website**.
   - **Paste cookies:** copy `li_at` and `JSESSIONID` from DevTools and save them in the form on the page.
4. Paste a `linkedin.com/in/…` URL and fetch.

The session is stored in **that visitor’s browser** and sent only with their lookup. The server does not keep it.

**Server operator (optional fallback)**

You may still put `LINKEDIN_LI_AT` / `LINKEDIN_JSESSIONID` in Render env vars so the site works even when a visitor has not connected. Set `API_KEY` on a public URL so strangers cannot spend that session.

#### Option 2 — Browser extension (Chrome or Firefox)

1. Log into [linkedin.com](https://www.linkedin.com) in Chrome or Firefox.
2. Load the unpacked extension from `extension/`:
   - **Chrome:** `chrome://extensions` → **Developer mode** → **Load unpacked**.
   - **Firefox:** `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on** → `extension/manifest.json`.
3. Open your Profile Lens site (local or hosted) and keep that tab focused.
4. Click the **Profile Lens** icon → **Save to this website**.

#### Option 3 — Paste cookies on the website

1. Log into LinkedIn.
2. DevTools → Application/Storage → Cookies → `https://www.linkedin.com`.
3. Copy `li_at` and `JSESSIONID` (required). Optional: `liap`, `bcookie`, `lidc`, `li_a`.
4. On Profile Lens, open **Paste cookies**, paste, and click **Save connection**.

The user-agent is filled from this browser automatically.

### 2. Run locally (no Docker)

Docker is optional. On this machine you can start the API with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# paste session from Option 2 or Option 3 (see above)

make run
```

That runs `python -m uvicorn` from `.venv` with `PYTHONPATH=backend`. Equivalent:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ for the Vue frontend (`frontend/`).
The backend lives in `backend/app/` and exposes schema adapters so callers choose the JSON shape.
Open http://127.0.0.1:8000/docs for the interactive OpenAPI UI.

```bash
# Nested schema (default adapter)
curl -X POST 'http://127.0.0.1:8000/v1/profile?adapter=default' \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/YOUR_VANITY_SLUG/"}'

# Flat export-oriented schema
curl -X POST 'http://127.0.0.1:8000/v1/profile?adapter=profilelens' \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/YOUR_VANITY_SLUG/"}'
```

If `API_KEY` is set in `.env`, also send `-H 'X-API-Key: …'`.

### 3. Tests

```bash
pytest -q
```

Tests use fixture JSON only. They never call LinkedIn.

### 4. Deploy over HTTPS (Render)

1. Push this repo to GitHub (public, as required).
2. Create a [Render](https://render.com) Web Service from the repo. `render.yaml` + `Dockerfile` are included.
3. Set environment variables (do **not** commit them):
   - `LINKEDIN_LI_AT`
   - `LINKEDIN_JSESSIONID`
   - `LINKEDIN_USER_AGENT` (same browser that minted the cookies)
   - `LINKEDIN_LIAP` / `LINKEDIN_BCOOKIE` / `LINKEDIN_LIDC` / `LINKEDIN_LI_A` (optional; use if Render gets `401`/`403`)
   - `API_KEY` (recommended on a public URL)
4. Render provides a public `https://…onrender.com` URL. Health check: `GET /health`.

## API documentation

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Vue frontend (`frontend/`). |
| `GET` | `/ui/config` | Cookies / API key flags + available adapters (no secrets). |
| `GET` | `/health` | Liveness. `linkedinConfigured` is true when cookies are present. |
| `GET` | `/v1/adapters` | List schema adapters (`default`, `profilelens`). |
| `POST` | `/v1/profile?adapter=` | Body `{"url": "…"}`. Adapter controls `data` shape. |
| `GET` | `/v1/profile?url=&adapter=` | Same lookup via query params. |

### Response envelope

Every profile response looks like:

```json
{
  "adapter": "default",
  "data": { }
}
```

- `adapter=default` → nested profile (`experience[]`, `education[]`, …)
- `adapter=profilelens` → flat export fields (`companyName`, `jobTitle`, `linkedinSkillsLabel`, …) plus `experienceJson` / `educationJson` for full history


Optional header: `X-API-Key` (required when `API_KEY` is configured).

### Success (`200`)

```json
{
  "publicId": "ada-lovelace",
  "profileUrl": "https://www.linkedin.com/in/ada-lovelace/",
  "fullName": "Ada Lovelace",
  "firstName": "Ada",
  "lastName": "Lovelace",
  "headline": "Mathematician and first computer programmer",
  "location": "London, England",
  "about": "Wrote the first algorithm intended for a machine.",
  "pronouns": "she/her",
  "industry": "Computer Science",
  "profileImage": "https://media.licdn.com/…",
  "backgroundImage": "https://media.licdn.com/…",
  "experience": [
    {
      "title": "Analyst",
      "company": "Analytical Engine Co.",
      "location": "London",
      "description": "…",
      "employmentType": "Full-time",
      "dateRange": { "start": "1842-01", "end": "1852-06", "current": false }
    }
  ],
  "education": [],
  "skills": [{ "name": "Mathematics", "endorsementCount": 42 }],
  "certifications": [],
  "languages": [{ "name": "English", "proficiency": "Native or bilingual" }],
  "volunteer": [],
  "honors": []
}
```

Missing sections are empty arrays or `null`. The schema stays stable even when LinkedIn omits a block.

### Errors

| Status | `code` | When |
|--------|--------|------|
| 400 | `invalid_url` | Not a `linkedin.com/in/{slug}` URL. |
| 401 | `unauthorized` | Missing/invalid `X-API-Key`. |
| 401 | `session_expired` | LinkedIn cookies expired or rejected. |
| 404 | `not_found` | Profile missing or not visible to this session. |
| 429 | `rate_limited` / `linkedin_rate_limited` | Our limiter, or LinkedIn's. |
| 502 | `upstream_error` / `parse_error` | LinkedIn failed or payload could not be mapped. |
| 503 | `not_configured` | Cookies not set on the server. |

## Approach

This is a **pure reverse-engineered HTTP client**. It does **not** use a browser.

- No Playwright, Selenium, Puppeteer, or headless Chrome
- No rendering of `linkedin.com/in/{slug}` HTML
- No automated login flow
- The server issues `GET` requests straight to LinkedIn Voyager JSON endpoints
- Session cookies (`li_at`, `JSESSIONID`) are captured once from a normal logged-in browser — either the `extension/` helper (Option 2) or DevTools paste (Option 3) — and stored as env vars. The process never drives a browser.

`curl_cffi` is an HTTP library (libcurl). `impersonate="chrome"` only matches a TLS fingerprint so datacenter Python stacks are less likely to be blocked. It does not start Chromium or parse a profile page.

LinkedIn's public developer API is OAuth-scoped to the authenticated user and a small set of fields. It cannot implement "paste any profile URL → full page JSON".

After a member is logged in, the LinkedIn web app loads profile JSON from:

```
GET /voyager/api/identity/dash/profiles
    ?q=memberIdentity
    &memberIdentity={slug}
    &decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93
```

That is a Rest.li endpoint. The request mirrors the XHR the web app sends, but we replay it ourselves over HTTP:

- Cookies: `li_at` (session) and `JSESSIONID` (CSRF). Optional extras: `liap`, `bcookie`, `lidc`, `li_a` if a datacenter IP is pickier than a home session. Optional `LINKEDIN_USER_AGENT` should match the browser that minted `li_at` (Option 2 copies it; Option 3 you paste it).
- Header `csrf-token` = the `JSESSIONID` value without quotes.
- `accept: application/vnd.linkedin.normalized+json+2.1`
- `x-restli-protocol-version: 2.0.0`

The response is **normalized JSON**: a `data` object plus an `included` graph. Entities are typed (`$type`), for example:

- `…profile.Profile` — name, headline, about, images, location
- `…profile.Position` / `Education` / `Skill` / `Certification` / `Language`
- `…profile.VolunteerExperience` / `Honor`

Image URLs are `vectorImage.rootUrl + artifacts[].fileIdentifyingUrlPathSegment` (largest artifact).

If the dash decoration id fails (LinkedIn versions these strings), the client retries a short list of known decorations, then falls back to the older `GET /voyager/api/identity/profiles/{slug}/profileView` payload, which uses `positionView` / `educationView` / etc.

The dash payload often truncates skills, certifications, and languages. After the main profile GET succeeds, the client issues additional Voyager GETs in parallel (still no browser):

```
GET /voyager/api/identity/profiles/{slug}/skills
GET /voyager/api/identity/profiles/{slug}/skillCategory
GET /voyager/api/identity/profiles/{slug}/certifications
GET /voyager/api/identity/profiles/{slug}/languages
GET /voyager/api/identity/profiles/{slug}/honors
GET /voyager/api/identity/profiles/{slug}/volunteerExperiences
```

A missing or failing section request is ignored; the core profile is still returned. All of these shapes are merged and mapped onto **one** response schema in `app/linkedin/parser.py`.

We do not wrap a third-party scraper SDK. The Voyager client, URL parser, and graph mapper are this repo.

Other production-shaped details:

- In-memory TTL cache so repeat lookups do not spend the LinkedIn session.
- Process-local rate limit on upstream fetches.
- Secrets only via environment variables.

## Known limitations

- **Not an official LinkedIn API.** Decoration IDs, entity types, and anti-bot checks change without notice.
- **Session cookies expire** (often within days/weeks). The operator must refresh `li_at` / `JSESSIONID` (and any optional extras).
- **Account risk.** Automated use can trigger checkpoints, rate limits, or restriction. Use a throwaway account if possible; keep `RATE_LIMIT_PER_MINUTE` low.
- **Visibility.** You only see what that logged-in account can see. Locked / out-of-network profiles return fewer fields or `not_found`.
- **ToS.** LinkedIn's terms generally disallow scraping. This project exists to demonstrate reverse-engineering and API design for a hiring challenge, not as a commercial scraper.
- **Contact info** (email, phone) is usually a separate, more-restricted endpoint and is not returned.
- **Free-tier hosting.** Render may cold-start; LinkedIn may treat cloud IPs more strictly than a home browser. If that happens, add `LINKEDIN_LIAP` / `LINKEDIN_BCOOKIE` / `LINKEDIN_LIDC` / `LINKEDIN_LI_A` from the same browser session.
- **In-memory cache/limits** are per process. Multiple replicas do not share them.

## Project layout

```
backend/app/              # FastAPI backend only
  main.py                 # app factory, mounts frontend assets, /health
  adapters/               # schema adapters (default, profilelens)
    mappings/*.json       # declarative field maps (edit these to change JSON shape)
    mapping_schema.py     # validates mapping documents
    json_mapper.py        # applies mapping JSON → output dict
  linkedin/               # Voyager HTTP client + parser
  routers/profile.py      # /v1/profile + /v1/adapters
  schemas.py              # canonical model + envelope types
frontend/                 # Vue 3 UI (separate from backend)
  index.html
  css/styles.css
  js/api.js               # API client
  js/app.js               # Vue app
extension/                # Chrome/Firefox session helper (reads cookies locally)
  manifest.json
  popup.html / popup.js
tests/                    # fixtures, no live LinkedIn calls
Dockerfile / render.yaml  # HTTPS deploy
```
