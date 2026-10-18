// Run in the connected Figma Email Kit file before read-email.js when changing
// issue metadata. Select Email/Issue, or replace this with its exact node ID.
// Announcement copy and the email's title are preserved.
const ISSUE_NODE_ID = "";
figma.skipInvisibleInstanceChildren = false;
const issue = ISSUE_NODE_ID
  ? await figma.getNodeByIdAsync(ISSUE_NODE_ID)
  : figma.currentPage.selection[0];
if (!issue || issue.type !== "FRAME" || issue.name !== "Email/Issue") {
  throw new Error("Select the Email/Issue frame, or set ISSUE_NODE_ID.");
}
let page = issue.parent;
while (page && page.type !== "PAGE") page = page.parent;
if (!page) throw new Error("The selected issue has no page.");
await figma.setCurrentPageAsync(page);

async function block(name) {
  const matches = [];
  for (const child of issue.children) {
    if (child.type !== "INSTANCE") continue;
    const main = await child.getMainComponentAsync();
    const owner = main && main.parent && main.parent.type === "COMPONENT_SET"
      ? main.parent : main;
    if (owner && owner.name === "Email/" + name) matches.push(child);
  }
  if (matches.length !== 1) throw new Error("Issue needs one Email/" + name + ".");
  return matches[0];
}
function field(parent, name) {
  const matches = parent.findAllWithCriteria({ types: ["TEXT"] })
    .filter(node => node.name === name);
  if (matches.length !== 1) throw new Error("Expected one " + name + " field.");
  return matches[0];
}
const settings = await block("Settings");
const title = await block("Title");
const header = await block("Header");
const meta = Object.fromEntries(["subject", "date", "url", "quarter"]
  .map(name => [name, field(settings, name).characters.trim()]));
for (const [name, value] of Object.entries(meta)) {
  if (!value || /[\r\n\x00]/.test(value)) {
    throw new Error("Issue " + name + " must be nonempty single-line text.");
  }
}
if (!/^\/emails\/[a-zA-Z0-9_-]+\/[a-zA-Z0-9_-]+\.html$/.test(meta.url)) {
  throw new Error("Issue URL must be /emails/<quarter>/<issue>.html.");
}
const date = meta.date.match(/^(\d{4})-(\d{2})-(\d{2})T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/);
if (!date || !Number.isFinite(new Date(meta.date).getTime())) {
  throw new Error("Send date needs an ISO timestamp with an explicit timezone.");
}
const year = Number(date[1]), month = Number(date[2]), day = Number(date[3]);
const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
if (month < 1 || month > 12 || day < 1 || day > daysInMonth) {
  throw new Error("Send date contains an invalid calendar date.");
}
// Use the written date prefix so an offset near midnight cannot change the day.
const months = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const eyebrow = field(title, "eyebrow");
const browser = field(header, "browserLink");
const fonts = [...new Map([eyebrow, browser]
  .flatMap(node => node.getStyledTextSegments(["fontName"]))
  .map(segment => [JSON.stringify(segment.fontName), segment.fontName])).values()];
await Promise.all(fonts.map(font => figma.loadFontAsync(font)));
const value = (meta.quarter + " · " + months[month - 1] + " " + day + ", " + year).toUpperCase();
const property = eyebrow.componentPropertyReferences && eyebrow.componentPropertyReferences.characters;
if (property) title.setProperties({ [property]: value });
else eyebrow.characters = value;
browser.characters = "View in browser";
browser.setRangeHyperlink(0, browser.characters.length, {
  type: "URL", value: "https://ballroom.stanford.edu" + meta.url
});
browser.setRangeTextDecoration(0, browser.characters.length, "UNDERLINE");
return {
  createdNodeIds: [],
  mutatedNodeIds: [...new Set([eyebrow.id, browser.id, ...(property ? [title.id] : [])])],
  issueId: issue.id,
  eyebrow: value,
  browserUrl: "https://ballroom.stanford.edu" + meta.url
};
