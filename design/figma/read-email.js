// Run through the connected Figma `use_figma` tool in the Email Kit file.
// Select the Email/Issue frame, or replace this value with its exact node ID.
// This script reads design content only. It never changes the design or sends mail.
const ISSUE_NODE_ID = "";
const selected = ISSUE_NODE_ID
  ? await figma.getNodeByIdAsync(ISSUE_NODE_ID)
  : figma.currentPage.selection[0];
if (!selected || selected.type !== "FRAME" || selected.name !== "Email/Issue") {
  throw new Error("Select the Email/Issue frame to export, or set ISSUE_NODE_ID.");
}
let page = selected.parent;
while (page && page.type !== "PAGE") page = page.parent;
if (!page) throw new Error("The selected issue has no page.");
await figma.setCurrentPageAsync(page);

const unsupportedEdits = [];
const collections = await figma.variables.getLocalVariableCollectionsAsync();
const variables = await figma.variables.getLocalVariablesAsync();
const collectionById = new Map(collections.map(c => [c.id, c]));
const variableById = new Map(variables.map(v => [v.id, v]));
const theme = { light: {}, dark: {}, type: {}, layout: {} };
const lightKeys = new Set(["background", "card", "text", "muted", "heading", "link", "notice", "table_header", "table_border", "warning", "celebrate"]);
const darkKeys = new Set(["background", "card", "text", "muted", "heading", "link", "notice", "table_header"]);
const typeKeys = new Set(["body_size", "body_line", "title_size", "title_line", "heading_size", "heading_line"]);
const toHex = color => "#" + [color.r, color.g, color.b]
  .map(value => Math.round(value * 255).toString(16).padStart(2, "0")).join("");

function resolve(variable, modeName, seen = new Set()) {
  if (!variable || seen.has(variable.id)) throw new Error("Missing or circular email token alias.");
  seen.add(variable.id);
  const collection = collectionById.get(variable.variableCollectionId);
  const mode = collection.modes.find(m => m.name.toLowerCase() === modeName.toLowerCase()) || collection.modes[0];
  const value = variable.valuesByMode[mode.modeId];
  return value && value.type === "VARIABLE_ALIAS"
    ? resolve(variableById.get(value.id), modeName, seen) : value;
}

for (const variable of variables) {
  const collection = collectionById.get(variable.variableCollectionId);
  if (!/email/i.test(collection.name) || /primitive/i.test(collection.name)) continue;
  // Semantic variables use schema token names as their final path component.
  const key = variable.name.split("/").pop();
  if (variable.resolvedType === "COLOR" && lightKeys.has(key)) {
    const light = resolve(variable, "Light");
    if (light.a !== undefined && light.a !== 1) unsupportedEdits.push(`Token ${key}: use opaque email colors.`);
    theme.light[key] = toHex(light);
    if (darkKeys.has(key)) theme.dark[key] = toHex(resolve(variable, "Dark"));
  } else if (variable.resolvedType === "FLOAT" && typeKeys.has(key)) {
    theme.type[key] = resolve(variable, "Value");
  } else if (variable.resolvedType === "FLOAT" && key === "content_padding") {
    theme.layout[key] = resolve(variable, "Value");
  }
}

async function read(node, context = "") {
  const result = { id: node.id, name: node.name, type: node.type };
  if ("visible" in node) result.visible = node.visible;
  if ("width" in node) result.width = node.width;
  if ("height" in node) result.height = node.height;
  if ("rotation" in node && node.rotation !== 0) unsupportedEdits.push(`${node.name}: rotation needs an email renderer mapping.`);
  if ("effects" in node && node.effects.some(e => e.visible !== false)) unsupportedEdits.push(`${node.name}: effects need an email renderer mapping.`);
  if (node.type === "INSTANCE") {
    const main = await node.getMainComponentAsync();
    const owner = main && main.parent && main.parent.type === "COMPONENT_SET" ? main.parent : main;
    result.componentName = owner ? owner.name : "";
    if (result.componentName && !result.componentName.startsWith("Email/")) {
      if (context !== "Email/Header") unsupportedEdits.push(`${node.name}: embedded components need an email renderer mapping.`);
      // The header's library logo is rendered from the original public PNGs.
      // Its internal paths/fonts are branding assets, not announcement fields.
      return result;
    }
    result.variants = {};
    for (const [key, property] of Object.entries(node.componentProperties)) {
      if (property.type === "VARIANT") result.variants[key.split("#")[0].toLowerCase()] = property.value;
    }
    // Content/style overrides must have a defined rendering path. Theme edits
    // belong in the supported variables, so arbitrary canvas fills/effects are
    // not silently discarded. Normal auto-layout reflow is not an override.
    const unsupported = new Set(["fills", "strokes", "effects", "rotation", "layoutMode", "paddingTop", "paddingBottom", "paddingLeft", "paddingRight", "itemSpacing", "fontSize", "lineHeight", "textAlignHorizontal"]);
    for (const override of node.overrides) {
      for (const property of override.overriddenFields) {
        if (unsupported.has(property)) unsupportedEdits.push(`${result.componentName} (${override.id}): change ${property} through supported email variables.`);
        if (result.componentName === "Email/Footer" && property === "characters") unsupportedEdits.push("Footer content comes from the site's mailing-list configuration.");
      }
    }
  }
  if (node.type === "TEXT") {
    result.characters = node.characters;
    result.segments = node.getStyledTextSegments(["fontName", "fontWeight", "textDecoration", "hyperlink", "listOptions", "indentation"]);
    for (const segment of result.segments) {
      if (segment.indentation && segment.listOptions && segment.listOptions.type !== "NONE") unsupportedEdits.push(`${node.name}: nested lists need an email renderer mapping.`);
      if (segment.fontName.family !== "Arimo" && !["Tinos", "Libre Baskerville", "Gelasio"].includes(segment.fontName.family)) {
        unsupportedEdits.push(`${node.name}: use the template's system-font-compatible styles.`);
      }
    }
    if (node.textAutoResize === "TRUNCATE") unsupportedEdits.push(`${node.name}: truncated text cannot be exported as a complete email.`);
  }
  if ("children" in node) {
    result.children = [];
    for (const child of node.children) result.children.push(await read(child, result.componentName || context));
  }
  return result;
}

const document = await read(selected);
if (selected.layoutMode !== "VERTICAL" || selected.width !== 600) unsupportedEdits.push("Keep the 600px vertical Email/Issue shell.");
for (const block of document.children) {
  if (block.componentName === "Email/Header") {
    for (const text of block.children || []) {
      if (text.type === "TEXT" && text.name === "browserLink" && text.characters !== "View in browser") unsupportedEdits.push("The browser link is generated from the issue URL; keep its standard label.");
    }
  }
}
return {
  schemaVersion: 1,
  fileKey: figma.fileKey,
  nodeId: selected.id,
  document,
  theme,
  unsupportedEdits: [...new Set(unsupportedEdits)]
};
