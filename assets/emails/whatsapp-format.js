// Convert the rendered announcement, including expanded Hugo shortcodes.
// Kept separate from the UI so conversion can be checked without a browser.
const BLOCKS = new Set(["P", "DIV", "SECTION", "ARTICLE", "FIGURE", "FIGCAPTION", "TR"]);
const SKIP = new Set(["SCRIPT", "STYLE", "TEMPLATE", "IMG"]);

function tidy(text) {
  return text.replace(/[ \t]+\n/g, "\n").replace(/\n[ \t]*\n/g, "\n\n")
    .replace(/\n{3,}/g, "\n\n").trim();
}

function mark(text, symbol) {
  // Keep formatting markers inside whitespace and on individual lines.
  return text.split("\n").map(line => line.trim()
    ? line.replace(/^(\s*)(.*?)(\s*)$/, `$1${symbol}$2${symbol}$3`)
    : line).join("\n");
}

function children(node, state) {
  return Array.from(node.childNodes).map(child => render(child, state)).join("");
}

function flat(node) {
  return children(node, { bold: true, italic: true, strike: true }).replace(/\s+/g, " ").trim();
}

function list(node, state) {
  let number = Number(node.getAttribute("start") || 1);
  return "\n" + Array.from(node.children).filter(child => child.tagName === "LI").map(item => {
    if (item.hasAttribute("value")) number = Number(item.getAttribute("value"));
    const prefix = node.tagName === "OL" ? `${number++}. ` : "- ";
    const lines = tidy(children(item, state)).split("\n");
    return prefix + lines.map((line, index) => index && line ? `  ${line}` : line).join("\n");
  }).join("\n") + "\n\n";
}

function table(node, state) {
  // Notices, buttons and photos use layout tables, not tabular content.
  if (node.getAttribute("role") === "presentation") return "\n\n" + children(node, state) + "\n\n";
  const rows = Array.from(node.querySelectorAll("tr")).filter(row => row.closest("table") === node);
  const cells = row => Array.from(row.children).filter(cell => ["TH", "TD"].includes(cell.tagName));
  const first = rows[0];
  const hasHeaders = first && (first.parentElement.tagName === "THEAD" || cells(first).every(cell => cell.tagName === "TH"));
  const headers = hasHeaders ? cells(first).map(flat) : [];
  const caption = Array.from(node.children).find(child => child.tagName === "CAPTION");
  const result = [];
  if (caption) result.push(mark(flat(caption), "*"));
  // A single lesson track needs its instructor printed only once.
  if (headers.length === 2) result.push(headers[1]);
  for (const row of rows.slice(hasHeaders ? 1 : 0)) {
    let column = 0;
    const values = cells(row).map((cell, index) => {
      const value = tidy(children(cell, state)).replace(/\s*\n\s*/g, " / ");
      const span = Number(cell.getAttribute("colspan") || 1);
      const label = index > 0 && headers.length > 2 && span === 1 ? headers[column] : "";
      column += span;
      return label ? `${label}: ${value}` : value;
    });
    result.push("- " + values.join(" — "));
  }
  return "\n\n" + result.join("\n") + "\n\n";
}

function render(node, state = {}) {
  if (node.nodeType === 3) return node.textContent.replace(/\s+/g, " ");
  if (node.nodeType !== 1) return "";
  const tag = node.tagName;
  if (SKIP.has(tag) || node.hasAttribute("hidden") || node.getAttribute("aria-hidden") === "true"
    || /display\s*:\s*none|visibility\s*:\s*hidden/i.test(node.getAttribute("style") || "")) return "";
  if (tag === "BR") return "\n";
  if (tag === "HR") return "\n\n";
  if (tag === "PRE") return "\n\n```\n" + node.textContent.trim() + "\n```\n\n";
  if (tag === "CODE") return "`" + node.textContent + "`";
  if (tag === "UL" || tag === "OL") return list(node, state);
  if (tag === "TABLE") return table(node, state);

  const heading = /^H[1-6]$/.test(tag);
  const bold = heading || ["STRONG", "B"].includes(tag) || /font-weight\s*:\s*(bold|[6-9]00)/i.test(node.getAttribute("style") || "");
  const italic = ["EM", "I"].includes(tag);
  const strike = ["DEL", "S", "STRIKE"].includes(tag);
  let content = children(node, { ...state, bold: state.bold || bold, italic: state.italic || italic, strike: state.strike || strike });
  if (bold && !state.bold) content = mark(content, "*");
  if (italic && !state.italic) content = mark(content, "_");
  if (strike && !state.strike) content = mark(content, "~");
  if (tag === "A") {
    const target = (node.getAttribute("href") || "").replace(/^(mailto:|tel:)/i, "");
    const label = content.trim() || node.querySelector("img")?.getAttribute("alt") || "";
    // Render links as plain URLs: WhatsApp does not use Markdown link labels.
    content = !target || label === target ? label : label ? `${label}: ${target}` : target;
  }
  if (tag === "BLOCKQUOTE") return "\n\n" + tidy(content).split("\n").map(line => `> ${line}`).join("\n") + "\n\n";
  if (heading || BLOCKS.has(tag)) return "\n\n" + content.trim() + "\n\n";
  if (tag === "TD" || tag === "TH") return content + "\n";
  return content;
}

export function announcementText(title, body, canonical) {
  const sections = [mark(title.trim(), "*"), tidy(children(body, {}))];
  if (canonical) sections.push(`Full announcement: ${canonical}`);
  return sections.filter(Boolean).join("\n\n") + "\n";
}
