import { fetchProfile, fetchUiConfig } from "./api.js";
import {
  SESSION_EVENT,
  clearSession,
  emptyForm,
  loadApiKey,
  loadSession,
  parsePastedBlock,
  saveApiKey,
  saveSession,
  toRequestSession,
} from "./session.js";

const VueLib = window.Vue;
if (!VueLib) {
  document.body.insertAdjacentHTML(
    "afterbegin",
    '<p class="boot-fail">Could not load the UI. Open <a href="http://127.0.0.1:8000/">http://127.0.0.1:8000/</a> (not a local HTML file).</p>'
  );
  throw new Error("Vue did not load");
}

const { createApp, computed, nextTick, onMounted, ref } = VueLib;

const EXAMPLES = [
  { label: "williamhgates", slug: "williamhgates", url: "https://www.linkedin.com/in/williamhgates/" },
  { label: "satyanadella", slug: "satyanadella", url: "https://www.linkedin.com/in/satyanadella/" },
];

createApp({
  setup() {
    const profileUrl = ref("");
    const apiKey = ref("");
    const apiKeyRequired = ref(false);
    const linkedinConfigured = ref(false);
    const loading = ref(false);
    const status = ref("Loading…");
    const statusIsError = ref(false);
    const profile = ref(null);
    const activeAdapter = ref("default");
    const availableAdapters = ref([]);
    const view = ref("pretty");
    const resultEl = ref(null);
    const copyLabel = ref("Copy JSON");
    const examples = EXAMPLES;
    const sessionMethod = ref("extension");
    const storedSession = ref(loadSession());
    const sessionForm = ref(emptyForm());

    const browserConnected = computed(() => Boolean(storedSession.value?.liAt && storedSession.value?.jsessionid));
    const canLookup = computed(() => browserConnected.value || linkedinConfigured.value);
    const lookupButtonLabel = computed(() => {
      if (loading.value) return "Fetching…";
      if (!canLookup.value) return "Connect first";
      return "Fetch profile";
    });
    const sessionPillLabel = computed(() => {
      if (browserConnected.value) return "Connected in this browser";
      if (linkedinConfigured.value) return "Using the host’s LinkedIn session";
      return "Not connected";
    });
    const sessionPillClass = computed(() => {
      if (browserConnected.value || linkedinConfigured.value) return "ok";
      return "off";
    });

    const isNested = computed(() => activeAdapter.value === "default");

    const outputFields = computed(() => {
      if (isNested.value) {
        return [
          "fullName",
          "headline",
          "location",
          "about",
          "profileImage",
          "experience[]",
          "education[]",
          "skills[]",
          "certifications[]",
          "languages[]",
          "volunteer[]",
          "honors[]",
        ];
      }
      return [
        "fullName",
        "headline",
        "companyName",
        "jobTitle",
        "linkedinSchoolName",
        "linkedinSkillsLabel",
        "experienceJson",
        "educationJson",
      ];
    });

    const metaLine = computed(() => {
      const p = profile.value;
      if (!p || !isNested.value) return "";
      return [p.location, p.industry, p.pronouns].filter(Boolean).join(" · ");
    });

    const coverStyle = computed(() => {
      const url = isNested.value
        ? profile.value?.backgroundImage
        : profile.value?.backgroundImageUrl;
      if (!url) return {};
      const safe = String(url).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
      return {
        backgroundImage: `linear-gradient(120deg, rgba(15,124,114,0.35), rgba(11,31,42,0.45)), url("${safe}")`,
      };
    });

    const displayName = computed(() => {
      const p = profile.value;
      if (!p) return "";
      return p.fullName || p.publicId || p.linkedinProfileSlug || "Unknown";
    });

    const displayHeadline = computed(() => profile.value?.headline || "");

    const displayImage = computed(() =>
      isNested.value ? profile.value?.profileImage : profile.value?.linkedinProfileImageUrl
    );

    const profileLink = computed(() =>
      isNested.value ? profile.value?.profileUrl : profile.value?.linkedinProfileUrl
    );

    const prettyJson = computed(() =>
      profile.value
        ? JSON.stringify({ adapter: activeAdapter.value, data: profile.value }, null, 2)
        : ""
    );

    const currentExperience = computed(() => {
      const list = profile.value?.experience || [];
      return list.find((item) => item.dateRange?.current) || list[0] || null;
    });

    const latestEducation = computed(() => (profile.value?.education || [])[0] || null);

    const overviewBits = computed(() => {
      const p = profile.value;
      if (!p) return [];
      if (!isNested.value) {
        return [
          { label: "Current title", value: p.jobTitle },
          { label: "Company", value: p.companyName },
          { label: "School", value: p.linkedinSchoolName },
          { label: "Industry", value: p.industry },
        ].filter((bit) => bit.value);
      }
      const bits = [];
      const job = currentExperience.value;
      const edu = latestEducation.value;
      if (job?.title) bits.push({ label: "Current title", value: job.title });
      if (job?.company) bits.push({ label: "Company", value: job.company });
      if (edu?.school) bits.push({ label: "School", value: edu.school });
      if (p.industry) bits.push({ label: "Industry", value: p.industry });
      return bits;
    });

    const sectionCounts = computed(() => {
      const p = profile.value;
      if (!p) return [];
      if (!isNested.value) {
        return [
          { label: "roles", count: p.experienceCount || 0 },
          { label: "schools", count: p.educationCount || 0 },
          { label: "skills", count: p.skillsCount || 0 },
        ].filter((row) => row.count > 0);
      }
      return [
        { label: "roles", count: (p.experience || []).length },
        { label: "schools", count: (p.education || []).length },
        { label: "skills", count: (p.skills || []).length },
        { label: "certs", count: (p.certifications || []).length },
        { label: "languages", count: (p.languages || []).length },
      ].filter((row) => row.count > 0);
    });

    onMounted(() => {
      apiKey.value = loadApiKey();
      window.addEventListener(SESSION_EVENT, syncStoredSession);
      window.addEventListener("storage", syncStoredSession);
      loadConfig();
    });

    function syncStoredSession() {
      storedSession.value = loadSession();
      refreshReadyStatus();
    }

    function refreshReadyStatus() {
      if (browserConnected.value) {
        setStatus("Connected — paste a LinkedIn profile URL.");
      } else if (linkedinConfigured.value) {
        setStatus("Ready — paste a public LinkedIn profile URL.");
      } else {
        setStatus("Connect LinkedIn below to look up profiles.", true);
      }
    }

    async function loadConfig() {
      try {
        const cfg = await fetchUiConfig();
        apiKeyRequired.value = Boolean(cfg.apiKeyRequired);
        linkedinConfigured.value = Boolean(cfg.linkedinConfigured);
        availableAdapters.value = cfg.adapters || [];
        activeAdapter.value = cfg.defaultAdapter || "default";
        if (apiKeyRequired.value && !apiKey.value) {
          apiKey.value = loadApiKey();
        }
        refreshReadyStatus();
      } catch {
        setStatus("Could not load UI config.", true);
      }
    }

    function useExample(url) {
      profileUrl.value = url;
    }

    async function onFetchProfile() {
      const url = profileUrl.value.trim();
      if (!url || loading.value) return;

      loading.value = true;
      profile.value = null;
      view.value = activeAdapter.value === "default" ? "pretty" : "json";
      copyLabel.value = "Copy JSON";
      setStatus(`Fetching with adapter “${activeAdapter.value}”…`);

      try {
        const envelope = await fetchProfile({
          url,
          apiKey: apiKey.value,
          adapter: activeAdapter.value,
          session: toRequestSession(storedSession.value),
        });
        activeAdapter.value = envelope.adapter || activeAdapter.value;
        profile.value = envelope.data;
        setStatus(
          `Loaded via ${envelope.adapter}: ${envelope.data.fullName || envelope.data.linkedinProfileSlug || "profile"}.`
        );
        await nextTick();
        resultEl.value?.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        const message = err.message || "Lookup failed.";
        setStatus(message, true);
        if (/signed you out|session_expired|Connect LinkedIn/i.test(message)) {
          document.getElementById("connect")?.scrollIntoView({ behavior: "smooth" });
        }
      } finally {
        loading.value = false;
      }
    }

    function setStatus(text, isError = false) {
      status.value = text;
      statusIsError.value = isError;
    }

    function persistApiKey() {
      saveApiKey(apiKey.value);
    }

    function onSessionPaste(event) {
      const text = event.clipboardData?.getData("text") || "";
      const parsed = parsePastedBlock(text);
      if (!parsed) return;
      event.preventDefault();
      sessionForm.value = parsed;
    }

    function savePastedSession() {
      const form = sessionForm.value;
      if (!form.liAt.trim() || !form.jsessionid.trim()) {
        setStatus("Paste both li_at and JSESSIONID.", true);
        return;
      }
      saveSession({
        liAt: form.liAt.trim(),
        jsessionid: form.jsessionid.trim(),
        userAgent: form.userAgent.trim() || navigator.userAgent,
        liap: form.liap.trim(),
        bcookie: form.bcookie.trim(),
        lidc: form.lidc.trim(),
        liA: form.liA.trim(),
      });
      storedSession.value = loadSession();
      sessionForm.value = emptyForm();
      refreshReadyStatus();
    }

    function disconnectSession() {
      clearSession();
      storedSession.value = null;
      sessionForm.value = emptyForm();
      refreshReadyStatus();
    }

    function joinBits(parts, sep = " · ") {
      return (parts || []).filter(Boolean).join(sep);
    }

    function formatRange(range) {
      if (!range) return "";
      const start = range.start || "";
      const end = range.current ? "Present" : range.end || "";
      if (start && end) return `${start} – ${end}`;
      return start || end;
    }

    async function copyJson() {
      if (!profile.value) return;
      try {
        await navigator.clipboard.writeText(prettyJson.value);
        copyLabel.value = "Copied";
        setTimeout(() => {
          copyLabel.value = "Copy JSON";
        }, 1600);
      } catch {
        setStatus("Could not copy to clipboard.", true);
      }
    }

    function downloadJson() {
      if (!profile.value) return;
      const slug = profile.value.publicId || profile.value.linkedinProfileSlug || "profile";
      triggerDownload(
        `${slug}-${activeAdapter.value}.json`,
        prettyJson.value,
        "application/json;charset=utf-8"
      );
    }

    function downloadCsv() {
      if (!profile.value) return;
      const slug = profile.value.publicId || profile.value.linkedinProfileSlug || "profile";
      const csv = isNested.value
        ? nestedToCsv(profile.value)
        : flatToCsv(profile.value);
      triggerDownload(`${slug}-${activeAdapter.value}.csv`, csv, "text/csv;charset=utf-8");
    }

    function triggerDownload(filename, contents, mime) {
      const blob = new Blob([contents], { type: mime });
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(href);
    }

    function nestedToCsv(p) {
      const job = (p.experience || []).find((item) => item.dateRange?.current) || (p.experience || [])[0] || {};
      const school = (p.education || [])[0] || {};
      return flatToCsv({
        firstName: p.firstName || "",
        lastName: p.lastName || "",
        fullName: p.fullName || "",
        headline: p.headline || "",
        location: p.location || "",
        industry: p.industry || "",
        linkedinDescription: p.about || "",
        linkedinProfileUrl: p.profileUrl || "",
        linkedinProfileSlug: p.publicId || "",
        companyName: job.company || "",
        jobTitle: job.title || "",
        linkedinSchoolName: school.school || "",
        linkedinSkillsLabel: (p.skills || []).map((s) => s.name).join(" | "),
        experienceCount: (p.experience || []).length,
        educationCount: (p.education || []).length,
      });
    }

    function flatToCsv(row) {
      const headers = Object.keys(row);
      const escape = (value) => {
        const text = typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "");
        return `"${text.replace(/"/g, '""')}"`;
      };
      return `${headers.join(",")}\n${headers.map((h) => escape(row[h])).join(",")}\n`;
    }

    return {
      profileUrl,
      apiKey,
      apiKeyRequired,
      loading,
      status,
      statusIsError,
      profile,
      activeAdapter,
      availableAdapters,
      isNested,
      view,
      resultEl,
      copyLabel,
      outputFields,
      examples,
      sessionMethod,
      linkedinConfigured,
      browserConnected,
      canLookup,
      lookupButtonLabel,
      sessionPillLabel,
      sessionPillClass,
      sessionForm,
      persistApiKey,
      onSessionPaste,
      savePastedSession,
      disconnectSession,
      metaLine,
      coverStyle,
      displayName,
      displayHeadline,
      displayImage,
      profileLink,
      prettyJson,
      overviewBits,
      sectionCounts,
      useExample,
      onFetchProfile,
      joinBits,
      formatRange,
      copyJson,
      downloadJson,
      downloadCsv,
    };
  },
}).mount("#app");
