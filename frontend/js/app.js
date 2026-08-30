import { fetchProfile, fetchUiConfig } from "./api.js?v=ux-guide";
import {
  collectFromPaths,
  fillTemplate,
  isExpandable,
  mappingDocumentFromPreset,
  mappingDocumentToTemplate,
  makeObjectNode,
  makeValueNode,
  normalizeMappingDocument,
  OUTPUT_PATH,
  previewLeaf,
  sourceKeyFromPath,
  templateToTree,
  validateMappingDocument,
} from "./schemaEditor.js";
import {
  ADAPTER_NAME,
  FALLBACK_SCHEMA,
  RESERVED_ADAPTERS,
  SESSION_EVENT,
  clearSession,
  cloneRows,
  emptyForm,
  loadApiKey,
  loadSchemaRows,
  loadSession,
  loadUserAdapters,
  parsePastedBlock,
  saveApiKey,
  saveSchemaRows,
  saveSession,
  saveUserAdapters,
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

const { createApp, computed, nextTick, onMounted, ref, watch } = VueLib;

const SchemaTree = {
  name: "SchemaTree",
  template: "#schema-tree-template",
  props: {
    nodes: { type: Array, required: true },
    sourceOptions: { type: Array, required: true },
    depth: { type: Number, default: 0 },
  },
  setup(props) {
    function isInvalidKey(key) {
      return Boolean(key) && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(key);
    }
    function addField(list) {
      list.push(makeValueNode("", props.sourceOptions[0]?.path || "fullName"));
    }
    function addObject(list) {
      list.push(makeObjectNode("group", [makeValueNode("name", "fullName")]));
    }
    function removeAt(index) {
      props.nodes.splice(index, 1);
    }
    return { isInvalidKey, addField, addObject, removeAt };
  },
};

const SourceTree = {
  name: "SourceTree",
  template: "#source-tree-template",
  props: {
    value: { required: true },
    path: { type: String, default: "" },
    depth: { type: Number, default: 0 },
  },
  emits: ["pick"],
  setup(props, { emit }) {
    const entries = computed(() => {
      const value = props.value;
      const prefix = props.path;
      if (value == null) return [];
      if (Array.isArray(value)) {
        return value.slice(0, 12).map((item, index) => {
          const next = prefix ? `${prefix}.${index}` : String(index);
          return {
            key: String(index),
            path: next,
            preview: previewLeaf(item),
            child: isExpandable(item) ? item : null,
          };
        });
      }
      if (typeof value === "object") {
        return Object.entries(value).map(([key, item]) => {
          const next = prefix ? `${prefix}.${key}` : key;
          return {
            key,
            path: next,
            preview: previewLeaf(item),
            child: isExpandable(item) ? item : null,
          };
        });
      }
      return [];
    });
    function pick(entry) {
      emit("pick", entry);
    }
    return { entries, pick };
  },
};

const EXAMPLES = [
  { label: "williamhgates", slug: "williamhgates", url: "https://www.linkedin.com/in/williamhgates/" },
  { label: "satyanadella", slug: "satyanadella", url: "https://www.linkedin.com/in/satyanadella/" },
];

const app = createApp({
  setup() {
    const profileUrl = ref("");
    const apiKey = ref("");
    const apiKeyRequired = ref(false);
    const linkedinConfigured = ref(false);
    const hostSessionForUi = ref(false);
    const loading = ref(false);
    const status = ref("Loading…");
    const statusIsError = ref(false);
    const profile = ref(null);
    const activeAdapter = ref("profilelens");
    const availableAdapters = ref([]);
    const view = ref("response");
    const resultEl = ref(null);
    const copyLabel = ref("Copy JSON");
    const examples = EXAMPLES;
    const sessionMethod = ref("extension");
    const storedSession = ref(loadSession());
    const sessionForm = ref(emptyForm());
    const schemaFields = ref([]);
    const schemaPresets = ref({});
    const userAdapters = ref(loadUserAdapters());
    const adapterNameDraft = ref("");
    const adapterTemplate = ref(
      mappingDocumentFromPreset(null, loadSchemaRows() || cloneRows(FALLBACK_SCHEMA))
    );
    const schemaTree = ref(templateToTree(mappingDocumentToTemplate(adapterTemplate.value)));
    const jsonError = ref("");
    const jsonIssues = ref([]);
    const jsonDraft = ref("");
    const editorReady = ref(null);
    const jsonEditorEl = ref(null);
    const resultAdapter = ref("");
    const sourceProfile = ref(null);
    const failedLogos = ref({});
    let persistSchema = false;
    let jsonEditor = null;
    let settingEditor = false;
    watch(
      adapterTemplate,
      (doc) => {
        if (persistSchema && Array.isArray(doc?.fields)) saveSchemaRows(doc.fields);
      },
      { deep: true }
    );

    const browserConnected = computed(() => Boolean(storedSession.value?.liAt && storedSession.value?.jsessionid));
    const canLookup = computed(() => browserConnected.value || hostSessionForUi.value);
    const flowStep = computed(() => {
      if (!canLookup.value) return 1;
      if (!sourceProfile.value && !profile.value) return 2;
      return 3;
    });

    function goToStep(step) {
      const ids = { 1: "connect", 2: "lookup", 3: "result", 4: "how-to" };
      const target =
        document.getElementById(ids[step]) ||
        (step === 3 ? document.getElementById("lookup") : null);
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    const lookupButtonLabel = computed(() => {
      if (loading.value) return "Fetching…";
      if (!canLookup.value) return "Connect first";
      return "Fetch profile";
    });
    const sessionPillLabel = computed(() => {
      if (browserConnected.value) return "Connected in this browser";
      if (hostSessionForUi.value) return "Using the host’s LinkedIn session";
      if (linkedinConfigured.value) return "Connect LinkedIn here (host session is local-only)";
      return "Not connected";
    });
    const sessionPillClass = computed(() => {
      if (browserConnected.value || hostSessionForUi.value) return "ok";
      return "off";
    });

    const visibleAdapters = computed(() => {
      const builtins = (availableAdapters.value || []).filter((adapter) => adapter.name !== "custom");
      const extras = userAdapters.value.map((adapter) => ({
        name: adapter.name,
        description: adapter.description || "Your saved adapter",
      }));
      return [...builtins, ...extras];
    });

    const knownPaths = computed(() => {
      const paths = (schemaFields.value || []).map((field) => field.path);
      for (const preset of Object.values(schemaPresets.value || {})) {
        for (const field of preset.fields || []) {
          const from = field.from || field.from_;
          if (from) paths.push(String(from).replace(/^\$/, ""));
        }
      }
      return [...new Set(paths)];
    });

    watch(knownPaths, () => {
      jsonIssues.value = validateMappingDocument(adapterTemplate.value);
    });

    const isUserAdapter = computed(() =>
      userAdapters.value.some((adapter) => adapter.name === activeAdapter.value)
    );

    const contextNames = computed(() => {
      const names = Object.keys(schemaPresets.value.profilelens?.context || {});
      return names.length ? names : ["currentJob", "previousJob", "school"];
    });

    const presetTemplate = computed(() => {
      if (isUserAdapter.value) {
        const saved = userAdapters.value.find((adapter) => adapter.name === activeAdapter.value)?.template;
        return normalizeMappingDocument(saved, contextNames.value);
      }
      return mappingDocumentFromPreset(
        schemaPresets.value[activeAdapter.value] || schemaPresets.value.profilelens,
        FALLBACK_SCHEMA
      );
    });

    const profilelensMappingJson = computed(() =>
      JSON.stringify(mappingDocumentFromPreset(schemaPresets.value.profilelens, FALLBACK_SCHEMA), null, 2)
    );

    const schemaDirty = computed(() => {
      const current = (adapterTemplate.value?.fields || [])
        .map((row) => `${row.to}\0${row.from || row.from_ || ""}`)
        .sort()
        .join("\n");
      const preset = (presetTemplate.value?.fields || [])
        .map((row) => `${row.to}\0${row.from || row.from_ || ""}`)
        .sort()
        .join("\n");
      return current !== preset;
    });

    const mappingHasFields = computed(
      () =>
        Array.isArray(adapterTemplate.value?.fields) &&
        adapterTemplate.value.fields.some((row) => row?.to && (row.from || row.from_))
    );

    const requestAdapter = computed(() => {
      if ((isUserAdapter.value || schemaDirty.value) && mappingHasFields.value) return "custom";
      return "profilelens";
    });

    const activeAdapterLabel = computed(() => {
      if (activeAdapter.value === "profilelens") return "Profile Lens";
      return activeAdapter.value;
    });

    const activeAdapterDescription = computed(() => {
      const fromList = visibleAdapters.value.find((adapter) => adapter.name === activeAdapter.value);
      return fromList?.description || schemaPresets.value.profilelens?.description || "";
    });

    const adapterBadge = computed(() => {
      if (jsonError.value) return { label: "Invalid JSON", cls: "edited" };
      if (jsonIssues.value.length) return { label: "Issues flagged", cls: "edited" };
      if (isUserAdapter.value && !schemaDirty.value) return { label: "Saved adapter", cls: "default" };
      if (schemaDirty.value) return { label: "Unsaved edits", cls: "edited" };
      return { label: activeAdapterLabel.value, cls: "default" };
    });

    const isNested = computed(() => {
      const p = linked.value;
      if (p) return Array.isArray(p.experience) || Array.isArray(p.education);
      return false;
    });

    const sourceOptions = computed(() => {
      const options = [...schemaFields.value];
      const known = new Set(options.map((field) => field.path));
      for (const path of collectFromPaths(schemaTree.value)) {
        if (path && !known.has(path)) {
          options.push({ path, label: path, group: "This schema" });
          known.add(path);
        }
      }
      return options;
    });

    const schemaPreview = computed(() => JSON.stringify(adapterTemplate.value, null, 2));

    const liveReturned = computed(() => {
      const source = sourceProfile.value;
      if (!source) return null;
      return fillTemplate(mappingDocumentToTemplate(adapterTemplate.value), source, contextNames.value);
    });

    const returnedPreview = computed(() => {
      if (liveReturned.value) return JSON.stringify(liveReturned.value, null, 2);
      return schemaPreview.value;
    });

    const linked = computed(() => sourceProfile.value || profile.value);

    const sourceJson = computed(() =>
      sourceProfile.value ? JSON.stringify(sourceProfile.value, null, 2) : ""
    );

    const outputFields = computed(() => {
      const keys = (adapterTemplate.value?.fields || []).map((row) => row.to).filter(Boolean);
      return keys.length ? keys : ["fullName"];
    });

    const metaLine = computed(() => {
      const p = linked.value;
      if (!p) return "";
      return [p.location, p.industry, p.pronouns].filter(Boolean).join(" · ");
    });

    const coverStyle = computed(() => {
      const url = linked.value?.backgroundImage || linked.value?.backgroundImageUrl;
      if (!url) return {};
      const safe = String(url).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
      return {
        backgroundImage: `linear-gradient(120deg, rgba(15,124,114,0.35), rgba(11,31,42,0.45)), url("${safe}")`,
      };
    });

    const displayName = computed(() => {
      const p = linked.value;
      if (!p) return "";
      return p.fullName || p.name || p.publicId || p.linkedinProfileSlug || "Unknown";
    });

    const displayHeadline = computed(() => linked.value?.headline || "");

    const displayImage = computed(
      () => linked.value?.profileImage || linked.value?.linkedinProfileImageUrl
    );

    const profileLink = computed(
      () => linked.value?.profileUrl || linked.value?.linkedinProfileUrl
    );

    const prettyJson = computed(() => {
      const data = liveReturned.value || profile.value;
      if (!data) return "";
      return JSON.stringify(
        { adapter: resultAdapter.value || requestAdapter.value, data },
        null,
        2
      );
    });

    const overviewBits = computed(() => {
      const p = linked.value;
      if (!p) return [];
      if (!Array.isArray(p.experience) && p.jobTitle) {
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
      const p = linked.value;
      if (!p) return [];
      if (Array.isArray(p.experience) || Array.isArray(p.education) || Array.isArray(p.skills)) {
        return [
          { label: "roles", count: (p.experience || []).length },
          { label: "schools", count: (p.education || []).length },
          { label: "skills", count: (p.skills || []).length },
          { label: "certs", count: (p.certifications || []).length },
          { label: "languages", count: (p.languages || []).length },
        ].filter((row) => row.count > 0);
      }
      return [
        { label: "roles", count: p.experienceCount || 0 },
        { label: "schools", count: p.educationCount || 0 },
        { label: "skills", count: p.skillsCount || 0 },
      ].filter((row) => row.count > 0);
    });

    const currentExperience = computed(() => {
      const list = linked.value?.experience || [];
      return list.find((item) => item.dateRange?.current) || list[0] || null;
    });

    const latestEducation = computed(() => (linked.value?.education || [])[0] || null);

    onMounted(async () => {
      apiKey.value = loadApiKey();
      window.addEventListener(SESSION_EVENT, syncStoredSession);
      window.addEventListener("storage", syncStoredSession);
      await loadConfig();
      await nextTick();
      initJsonEditor();
    });

    function syncStoredSession() {
      storedSession.value = loadSession();
      refreshReadyStatus();
    }

    function refreshReadyStatus() {
      if (browserConnected.value) {
        setStatus("Connected — paste a LinkedIn profile URL.");
      } else if (hostSessionForUi.value) {
        setStatus("Ready — paste a public LinkedIn profile URL.");
      } else {
        setStatus("Connect LinkedIn in step 1, then paste a profile URL.", true);
      }
    }

    async function loadConfig() {
      try {
        const cfg = await fetchUiConfig();
        apiKeyRequired.value = Boolean(cfg.apiKeyRequired);
        linkedinConfigured.value = Boolean(cfg.linkedinConfigured);
        hostSessionForUi.value = Boolean(cfg.hostSessionForUi);
        availableAdapters.value = cfg.adapters || [];
        schemaFields.value = cfg.schemaFields || [];
        schemaPresets.value = cfg.schemaPresets || {};
        const nextAdapter = cfg.defaultAdapter || "profilelens";
        activeAdapter.value = nextAdapter === "custom" ? "profilelens" : nextAdapter;
        const initial = mappingDocumentFromPreset(schemaPresets.value.profilelens, FALLBACK_SCHEMA);
        setEditorJson(JSON.parse(JSON.stringify(initial)));
        persistSchema = true;
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

      const adapter = requestAdapter.value;
      const schema = builtSchema();
      if (adapter === "custom") {
        const issues = validateMappingDocument(adapterTemplate.value);
        if (issues.length) {
          setStatus(issues[0].message, true);
          return;
        }
        if (jsonError.value) {
          setStatus("Fix JSON errors in the adapter editor first.", true);
          return;
        }
      }

      loading.value = true;
      profile.value = null;
      sourceProfile.value = null;
      failedLogos.value = {};
      view.value = "response";
      copyLabel.value = "Copy JSON";
      setStatus(`Fetching with adapter “${adapter}”…`);

      try {
        const envelope = await fetchProfile({
          url,
          apiKey: apiKey.value,
          adapter,
          session: toRequestSession(storedSession.value),
          schema,
        });
        resultAdapter.value = envelope.adapter || adapter;
        sourceProfile.value = envelope.source || null;
        profile.value = envelope.source
          ? fillTemplate(mappingDocumentToTemplate(adapterTemplate.value), envelope.source, contextNames.value)
          : envelope.data;
        const shown = sourceProfile.value || profile.value;
        setStatus(
          `Loaded ${shown.fullName || shown.name || shown.linkedinProfileSlug || "profile"} — edit adapter JSON to change what we return.`
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

    function pickSourceField(entry) {
      const key = sourceKeyFromPath(entry.path);
      const fields = [...(adapterTemplate.value.fields || [])];
      fields.push({ to: key, from: entry.path });
      setEditorJson({ ...adapterTemplate.value, fields });
      setStatus(`Mapped LinkedIn “${entry.path}” → ${key}.`);
    }

    function setEditorJson(json) {
      const plain = json && typeof json === "object" ? JSON.parse(JSON.stringify(json)) : json;
      adapterTemplate.value = plain;
      try {
        schemaTree.value = templateToTree(mappingDocumentToTemplate(plain), contextNames.value);
      } catch {
        /* keep previous tree if template is not a plain object */
      }
      jsonDraft.value = JSON.stringify(plain, null, 2);
      jsonError.value = "";
      jsonIssues.value = validateMappingDocument(plain);
      if (jsonEditor) {
        settingEditor = true;
        try {
          jsonEditor.set(plain);
        } finally {
          settingEditor = false;
        }
      }
    }

    function onEditorJson(json) {
      if (json === null || typeof json !== "object" || Array.isArray(json)) {
        jsonError.value =
          'Adapter JSON must match Profile Lens: { "fields": [{ "to": "name", "from": "fullName" }] }.';
        jsonIssues.value = [{ path: [], message: jsonError.value }];
        return;
      }
      if (!Array.isArray(json.fields)) {
        const converted = normalizeMappingDocument(json, contextNames.value);
        if (converted.fields.length) {
          if (schemaPresets.value.profilelens?.context) {
            converted.context = converted.context || schemaPresets.value.profilelens.context;
          }
          setEditorJson(converted);
          return;
        }
        jsonError.value =
          'Adapter JSON must match Profile Lens: { "fields": [{ "to": "name", "from": "fullName" }] }.';
        jsonIssues.value = [{ path: [], message: jsonError.value }];
        return;
      }
      jsonError.value = "";
      adapterTemplate.value = json;
      try {
        schemaTree.value = templateToTree(mappingDocumentToTemplate(json), contextNames.value);
      } catch (err) {
        jsonError.value = err.message || "Invalid adapter JSON.";
      }
      jsonDraft.value = JSON.stringify(json, null, 2);
      jsonIssues.value = validateMappingDocument(json);
    }

    function initJsonEditor() {
      const el = jsonEditorEl.value;
      if (!el || jsonEditor) return;
      if (typeof window.JSONEditor !== "function") {
        editorReady.value = false;
        jsonDraft.value = JSON.stringify(adapterTemplate.value, null, 2);
        return;
      }
      jsonEditor = new window.JSONEditor(el, {
        mode: "code",
        modes: ["code", "tree"],
        mainMenuBar: true,
        navigationBar: true,
        statusBar: true,
        onChange() {
          if (settingEditor || !jsonEditor) return;
          try {
            const json = jsonEditor.get();
            onEditorJson(json);
          } catch (err) {
            jsonError.value = err.message || "Invalid JSON.";
            jsonIssues.value = [];
          }
        },
        onValidate(json) {
          return validateMappingDocument(json);
        },
      });
      settingEditor = true;
      try {
      jsonEditor.set(JSON.parse(JSON.stringify(adapterTemplate.value)));
      } finally {
        settingEditor = false;
      }
      editorReady.value = true;
      jsonIssues.value = validateMappingDocument(adapterTemplate.value);
    }

    function applyFallbackDraft() {
      try {
        const parsed = JSON.parse(jsonDraft.value);
        onEditorJson(parsed);
      } catch (err) {
        jsonError.value = err.message || "Invalid JSON.";
        jsonIssues.value = [];
      }
    }

    function resetCustomRows() {
      setEditorJson(presetTemplate.value);
      jsonError.value = "";
    }

    function applyAdapterPreset() {
      if (!persistSchema) return;
      adapterNameDraft.value = isUserAdapter.value ? activeAdapter.value : "";
      resetCustomRows();
    }

    function saveUserAdapter() {
      const name = adapterNameDraft.value.trim().toLowerCase();
      if (!ADAPTER_NAME.test(name)) {
        setStatus("Adapter name: start with a letter, then letters, numbers, _ or - (max 32).", true);
        return;
      }
      if (RESERVED_ADAPTERS.has(name)) {
        setStatus(`“${name}” is built in. Choose another name.`, true);
        return;
      }
      let template;
      try {
        template = jsonEditor ? jsonEditor.get() : JSON.parse(jsonDraft.value);
      } catch (err) {
        setStatus(err.message || "Fix JSON errors before saving.", true);
        return;
      }
      if (!template || typeof template !== "object" || Array.isArray(template)) {
        setStatus(
          'Adapter JSON must match Profile Lens: { "fields": [{ "to": "name", "from": "fullName" }] }.',
          true
        );
        return;
      }
      const issues = validateMappingDocument(template);
      if (issues.length) {
        setStatus(issues[0].message, true);
        return;
      }
      const next = userAdapters.value.filter((adapter) => adapter.name !== name);
      next.push({ name, description: "Your adapter", template });
      next.sort((a, b) => a.name.localeCompare(b.name));
      userAdapters.value = next;
      saveUserAdapters(next);
      activeAdapter.value = name;
      adapterNameDraft.value = name;
      setEditorJson(template);
      setStatus(`Saved adapter “${name}”. Lookups return this JSON shape.`);
    }

    function deleteUserAdapter() {
      if (!isUserAdapter.value) return;
      const name = activeAdapter.value;
      const next = userAdapters.value.filter((adapter) => adapter.name !== name);
      userAdapters.value = next;
      saveUserAdapters(next);
      activeAdapter.value = "profilelens";
      adapterNameDraft.value = "";
      resetCustomRows();
      setStatus(`Deleted adapter “${name}”.`);
    }

    function builtSchema() {
      if (requestAdapter.value !== "custom") return null;
      const doc = normalizeMappingDocument(adapterTemplate.value, contextNames.value);
      const fields = (doc.fields || []).filter((row) => OUTPUT_PATH.test(row.to) && (row.from || row.from_));
      const schema = { fields };
      if (doc.context && Object.keys(doc.context).length) {
        schema.context = doc.context;
      } else {
        const preset = schemaPresets.value.profilelens;
        if (preset?.context && fields.some((field) => String(field.from).startsWith("$"))) {
          schema.context = preset.context;
        }
      }
      return schema;
    }

    function formatCustomValue(value) {
      if (value == null || value === "") return "—";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
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

    function showOrgLogo(url) {
      return Boolean(url) && !failedLogos.value[url];
    }

    function markLogoFailed(url) {
      if (!url || failedLogos.value[url]) return;
      failedLogos.value = { ...failedLogos.value, [url]: true };
    }

    function orgInitials(name) {
      const parts = String(name || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
      if (!parts.length) return "";
      if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
      return (parts[0][0] + parts[1][0]).toUpperCase();
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
      const text = prettyJson.value;
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        copyLabel.value = "Copied";
        setTimeout(() => {
          copyLabel.value = "Copy JSON";
        }, 1600);
      } catch {
        setStatus("Could not copy to clipboard.", true);
      }
    }

    function downloadJson() {
      const data = liveReturned.value || profile.value;
      if (!data) return;
      const slug = linked.value?.publicId || linked.value?.linkedinProfileSlug || "profile";
      triggerDownload(
        `${slug}-${resultAdapter.value || requestAdapter.value}.json`,
        prettyJson.value,
        "application/json;charset=utf-8"
      );
    }

    function downloadCsv() {
      const data = liveReturned.value || profile.value;
      if (!data) return;
      const slug = linked.value?.publicId || linked.value?.linkedinProfileSlug || "profile";
      const csv = Array.isArray(linked.value?.experience)
        ? nestedToCsv(linked.value)
        : flatToCsv(data);
      triggerDownload(
        `${slug}-${resultAdapter.value || requestAdapter.value}.csv`,
        csv,
        "text/csv;charset=utf-8"
      );
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
      visibleAdapters,
      isNested,
      schemaDirty,
      requestAdapter,
      activeAdapterLabel,
      activeAdapterDescription,
      resultAdapter,
      schemaPreview,
      returnedPreview,
      profilelensMappingJson,
      sourceProfile,
      sourceJson,
      liveReturned,
      linked,
      pickSourceField,
      sourceOptions,
      applyAdapterPreset,
      view,
      resultEl,
      copyLabel,
      outputFields,
      examples,
      sessionMethod,
      linkedinConfigured,
      hostSessionForUi,
      browserConnected,
      canLookup,
      flowStep,
      goToStep,
      lookupButtonLabel,
      sessionPillLabel,
      sessionPillClass,
      sessionForm,
      persistApiKey,
      resetCustomRows,
      saveUserAdapter,
      deleteUserAdapter,
      adapterNameDraft,
      adapterBadge,
      isUserAdapter,
      editorReady,
      jsonEditorEl,
      jsonDraft,
      jsonError,
      jsonIssues,
      applyFallbackDraft,
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
      formatCustomValue,
      showOrgLogo,
      markLogoFailed,
      orgInitials,
      joinBits,
      formatRange,
      copyJson,
      downloadJson,
      downloadCsv,
    };
  },
});
app.component("schema-tree", SchemaTree);
app.component("source-tree", SourceTree);
app.mount("#app");
