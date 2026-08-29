/** Live JSON-structure helpers: nested tree ↔ mapping rows ↔ $path template. */

export const OUTPUT_SEGMENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
export const OUTPUT_PATH = /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/;

export const ARRAY_SOURCES = new Set([
  "experience",
  "education",
  "skills",
  "certifications",
  "languages",
  "volunteer",
  "honors",
]);

let nodeId = 1;

export function nextNodeId() {
  return nodeId++;
}

export function makeValueNode(key, from) {
  return {
    id: nextNodeId(),
    kind: "value",
    key: key || "",
    from: from || "fullName",
    children: [],
  };
}

export function makeObjectNode(key, children = []) {
  return {
    id: nextNodeId(),
    kind: "object",
    key: key || "group",
    from: "",
    children,
  };
}

function bucketFor(root, objectAt, parts) {
  if (!parts.length) return root;
  const path = parts.join(".");
  if (objectAt.has(path)) return objectAt.get(path);

  const parent = bucketFor(root, objectAt, parts.slice(0, -1));
  const key = parts[parts.length - 1];
  let obj = parent.find((node) => node.key === key && node.kind === "object");
  if (!obj) {
    obj = makeObjectNode(key);
    parent.push(obj);
  }
  objectAt.set(path, obj.children);
  return obj.children;
}

export function rowsToTree(rows) {
  const root = [];
  const objectAt = new Map();
  for (const row of rows || []) {
    const to = String(row.to || "").trim();
    if (!to) continue;
    const parts = to.split(".");
    const key = parts.pop();
    const bucket = bucketFor(root, objectAt, parts);
    bucket.push(makeValueNode(key, row.from || row.from_ || "fullName"));
  }
  return root;
}

export function treeToRows(nodes, prefix = "") {
  const rows = [];
  for (const node of nodes || []) {
    const key = String(node.key || "").trim();
    if (!key) continue;
    const path = prefix ? `${prefix}.${key}` : key;
    if (node.kind === "object") {
      rows.push(...treeToRows(node.children || [], path));
      continue;
    }
    if (node.from) rows.push({ to: path, from: node.from });
  }
  return rows;
}

export function previewHint(from) {
  if (ARRAY_SOURCES.has(from) || String(from).endsWith("Json")) return [];
  return `$${from || "field"}`;
}

export function treeToPreview(nodes) {
  const out = {};
  for (const node of nodes || []) {
    if (!String(node.key || "").trim()) continue;
    out[node.key] = node.kind === "object" ? treeToPreview(node.children) : previewHint(node.from);
  }
  return out;
}

export const CONTEXT_ALIASES = ["currentJob", "previousJob", "school"];

export function templateValueToFrom(value, contextNames = CONTEXT_ALIASES) {
  if (typeof value !== "string" || !value) return "fullName";
  const raw = value.startsWith("$") ? value.slice(1) : value;
  if (!raw) return "";
  const alias = raw.split(".")[0];
  if (raw.startsWith("$") || contextNames.includes(alias)) {
    return raw.startsWith("$") ? raw : `$${raw}`;
  }
  return raw;
}

export function fromToTemplateValue(from) {
  const src = from || "fullName";
  return src.startsWith("$") ? src : `$${src}`;
}

export function liveContext(source) {
  const experience = Array.isArray(source?.experience) ? source.experience : [];
  const currentJob = experience.find((item) => item?.dateRange?.current) || experience[0] || null;
  const previousJob = experience.find((item) => item !== currentJob) || null;
  const school = Array.isArray(source?.education) ? source.education[0] || null : null;
  return { currentJob, previousJob, school };
}

export function treeToTemplate(nodes) {
  const out = {};
  for (const node of nodes || []) {
    if (!String(node.key || "").trim()) continue;
    out[node.key] =
      node.kind === "object" ? treeToTemplate(node.children) : fromToTemplateValue(node.from);
  }
  return out;
}

export function templateToTree(value, contextNames = CONTEXT_ALIASES) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Schema JSON must be an object, e.g. { \"name\": \"$fullName\" }.");
  }
  const nodes = [];
  for (const [key, child] of Object.entries(value)) {
    if (child !== null && typeof child === "object" && !Array.isArray(child)) {
      nodes.push(makeObjectNode(key, templateToTree(child, contextNames)));
      continue;
    }
    const from =
      typeof child === "string" && child ? templateValueToFrom(child, contextNames) : "fullName";
    nodes.push(makeValueNode(key, from || "fullName"));
  }
  return nodes;
}

export function collectFromPaths(nodes, acc = []) {
  for (const node of nodes || []) {
    if (node.kind === "object") collectFromPaths(node.children, acc);
    else if (node.from) acc.push(node.from);
  }
  return acc;
}

export function listOutputKeys(nodes, prefix = "") {
  const keys = [];
  for (const node of nodes || []) {
    const key = String(node.key || "").trim();
    if (!key) continue;
    const path = prefix ? `${prefix}.${key}` : key;
    if (node.kind === "object") keys.push(...listOutputKeys(node.children, path));
    else keys.push(path);
  }
  return keys;
}

export function dig(data, path) {
  if (!path) return data;
  let cur = data;
  for (const part of String(path).replace(/^\$/, "").split(".")) {
    if (cur == null) return null;
    if (Array.isArray(cur) && /^\d+$/.test(part)) {
      const idx = Number(part);
      cur = idx >= 0 && idx < cur.length ? cur[idx] : null;
      continue;
    }
    if (typeof cur === "object") {
      cur = cur[part];
      continue;
    }
    return null;
  }
  return cur;
}

export function assignPath(target, path, value) {
  const parts = String(path).split(".");
  let cur = target;
  for (const part of parts.slice(0, -1)) {
    if (!cur[part] || typeof cur[part] !== "object" || Array.isArray(cur[part])) {
      cur[part] = {};
    }
    cur = cur[part];
  }
  cur[parts[parts.length - 1]] = value;
}

export function applyRows(source, rows) {
  const out = {};
  for (const row of rows || []) {
    if (!row?.to || !row?.from) continue;
    assignPath(out, row.to, dig(source, row.from));
  }
  return out;
}

export function previewLeaf(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return `[${value.length}]`;
  if (typeof value === "object") return "{…}";
  const text = String(value);
  return text.length > 42 ? `${text.slice(0, 39)}…` : text;
}

export function isExpandable(value) {
  if (Array.isArray(value)) return value.length > 0;
  return Boolean(value) && typeof value === "object";
}

export function sourceKeyFromPath(path) {
  const last = String(path || "").split(".").pop() || "field";
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(last)) return last;
  return `field${last.replace(/[^A-Za-z0-9]/g, "") || "X"}`;
}

export function fillTemplate(template, source, contextNames = CONTEXT_ALIASES) {
  if (typeof template === "string") {
    const from = templateValueToFrom(template, contextNames);
    if (from.startsWith("$")) {
      const rest = from.slice(1);
      const alias = rest.split(".")[0];
      const nested = rest.includes(".") ? rest.slice(alias.length + 1) : "";
      const base = liveContext(source)[alias];
      return nested ? dig(base, nested) : base;
    }
    return dig(source, from);
  }
  if (Array.isArray(template)) {
    return template.map((item) => fillTemplate(item, source, contextNames));
  }
  if (template && typeof template === "object") {
    const out = {};
    for (const [key, child] of Object.entries(template)) {
      out[key] = fillTemplate(child, source, contextNames);
    }
    return out;
  }
  return template;
}

export function templateObjectToRows(value, prefix = "", contextNames = CONTEXT_ALIASES) {
  const rows = [];
  if (value === null || typeof value !== "object" || Array.isArray(value)) return rows;
  for (const [key, child] of Object.entries(value)) {
    if (!OUTPUT_SEGMENT.test(key)) continue;
    const path = prefix ? `${prefix}.${key}` : key;
    if (child !== null && typeof child === "object" && !Array.isArray(child)) {
      rows.push(...templateObjectToRows(child, path, contextNames));
      continue;
    }
    if (typeof child === "string" && child) {
      rows.push({ to: path, from: templateValueToFrom(child, contextNames) });
    }
  }
  return rows;
}

export function mappingDocumentFromPreset(preset, fallbackFields = []) {
  const source = preset?.fields?.length ? preset.fields : fallbackFields;
  const fields = source.map((row) => {
    const out = { to: row.to, from: row.from || row.from_ };
    if (row.transform) out.transform = row.transform;
    if (row.pluck != null) out.pluck = row.pluck;
    if (row.join != null) out.join = row.join;
    if (row.itemFormat) out.itemFormat = row.itemFormat;
    return out;
  });
  const doc = { fields };
  if (preset?.context && Object.keys(preset.context).length) {
    doc.context = preset.context;
  }
  return doc;
}

export function mappingDocumentToTemplate(doc) {
  const template = {};
  for (const row of doc?.fields || []) {
    if (!row?.to) continue;
    assignPath(template, row.to, fromToTemplateValue(row.from || row.from_ || "fullName"));
  }
  return template;
}

export function normalizeMappingDocument(json, contextNames = CONTEXT_ALIASES) {
  if (json && Array.isArray(json.fields)) return json;
  if (json && typeof json === "object" && !Array.isArray(json)) {
    const fields = templateObjectToRows(json, "", contextNames);
    if (fields.length) return { fields };
  }
  return { fields: [] };
}

export function validateMappingDocument(json) {
  if (json === null || typeof json !== "object" || Array.isArray(json)) {
    return [
      {
        path: [],
        message: 'Use the Profile Lens mapping shape: { "fields": [{ "to": "name", "from": "fullName" }] }.',
      },
    ];
  }
  if (!Array.isArray(json.fields)) {
    return [
      {
        path: ["fields"],
        message: 'Add a "fields" array. Each item is { "to": "outputKey", "from": "linkedinPath" }.',
      },
    ];
  }
  if (!json.fields.length) {
    return [
      {
        path: ["fields"],
        message: 'Add at least one field, e.g. { "to": "name", "from": "fullName" }.',
      },
    ];
  }
  const errors = [];
  json.fields.forEach((row, index) => {
    const path = ["fields", String(index)];
    if (!row || typeof row !== "object" || Array.isArray(row)) {
      errors.push({ path, message: "Each field must be an object { to, from }." });
      return;
    }
    if (!OUTPUT_PATH.test(String(row.to || ""))) {
      errors.push({
        path: path.concat("to"),
        message: '"to" must be a key like name or identity.name.',
      });
    }
    const from = String(row.from || row.from_ || "");
    if (!from) {
      errors.push({
        path: path.concat("from"),
        message: '"from" is the LinkedIn path, e.g. fullName or $currentJob.title.',
      });
    }
  });
  return errors;
}

export function templatesEqual(a, b) {
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

export function validateAdapterTemplate(json, knownPaths) {
  const errors = [];
  const known = new Set(knownPaths || []);

  function walk(node, path) {
    if (typeof node === "string") {
      if (!node.startsWith("$")) return;
      const raw = node.slice(1);
      if (!raw) {
        errors.push({ path, message: "Empty $path. Example: $fullName" });
        return;
      }
      if (!/^[A-Za-z_][A-Za-z0-9_.$]*$/.test(raw)) {
        errors.push({ path, message: `Invalid LinkedIn path "$${raw}".` });
        return;
      }
      if (known.size && !known.has(raw) && !raw.includes(".")) {
        if (CONTEXT_ALIASES.includes(raw)) return;
        errors.push({
          path,
          message: `Unknown LinkedIn field "$${raw}". Use a catalog path such as $fullName.`,
        });
      }
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((item, index) => walk(item, path.concat(String(index))));
      return;
    }
    if (node && typeof node === "object") {
      for (const [key, child] of Object.entries(node)) {
        if (!OUTPUT_SEGMENT.test(key)) {
          errors.push({
            path: path.concat(key),
            message: `Key "${key}" must start with a letter and use only letters, numbers, or underscores.`,
          });
        }
        walk(child, path.concat(key));
      }
    }
  }

  if (json === null || typeof json !== "object" || Array.isArray(json)) {
    return [{ path: [], message: "Adapter JSON must be an object, e.g. { \"name\": \"$fullName\" }." }];
  }
  walk(json, []);
  return errors;
}
