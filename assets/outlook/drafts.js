export const GRAPH_SCOPES = Object.freeze(["Mail.ReadWrite"]);
export const DRAFT_ENDPOINT = "https://graph.microsoft.com/v1.0/me/messages";
const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function applicationConfig(clientId, tenantId, redirectUri, origin) {
  if (!GUID.test(clientId) || !GUID.test(tenantId)) {
    throw new Error("Enter the application (client) ID and directory (tenant) ID from your Microsoft app registration.");
  }
  const redirect = new URL(redirectUri, origin);
  if (redirect.origin !== origin || redirect.search || redirect.hash ||
      (redirect.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(redirect.hostname))) {
    throw new Error("The Microsoft callback must use this website's HTTPS address.");
  }
  return {
    auth: {
      clientId,
      authority: "https://login.microsoftonline.com/" + tenantId,
      redirectUri: redirect.href
    },
    cache: { cacheLocation: "memoryStorage" }
  };
}

export function messageFor(payload, subject, recipient) {
  if (payload.schemaVersion !== 1 || typeof payload.html !== "string" ||
      !/^\s*<!doctype html>/i.test(payload.html) ||
      /<script[\s>]/i.test(payload.html) || /\son[a-z]+\s*=/i.test(payload.html)) {
    throw new Error("This announcement is missing its portable email export.");
  }
  if (typeof subject !== "string" || !subject.trim() || /[\r\n]/.test(subject)) {
    throw new Error("Enter a subject on one line.");
  }
  const addresses = String(recipient).split(/[;,]/).map(value => value.trim()).filter(Boolean);
  if (!addresses.length || addresses.some(address => !/^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$/.test(address))) {
    throw new Error("Enter recipient email addresses, separated by commas.");
  }
  return {
    subject: subject.trim(),
    body: { contentType: "HTML", content: payload.html },
    toRecipients: addresses.map(address => ({ emailAddress: { address } }))
  };
}

export async function loadAnnouncement(url, origin, fetchImpl = fetch) {
  const target = new URL(url, origin);
  if (target.origin !== origin) throw new Error("Announcements must come from this website.");
  const response = await fetchImpl(target.href, { redirect: "error", credentials: "omit" });
  if (!response.ok) throw new Error("Could not load this announcement. Refresh the page or choose another email.");
  return response.json();
}

export function outlookLink(value) {
  const link = new URL(value);
  if (link.protocol !== "https:" || !["outlook.office.com", "outlook.office365.com", "outlook.live.com"].includes(link.hostname)) {
    throw new Error("Outlook returned an unexpected draft link. Check your Drafts folder.");
  }
  return link.href;
}

export async function createHtmlDraft(accessToken, message, fetchImpl = fetch) {
  let response;
  try {
    response = await fetchImpl(DRAFT_ENDPOINT, {
      method: "POST",
      headers: { Authorization: "Bearer " + accessToken, "Content-Type": "application/json" },
      body: JSON.stringify(message),
      redirect: "error"
    });
  } catch {
    throw new Error("Could not confirm whether Outlook saved the draft. Check Drafts before trying again.");
  }
  if (!response.ok) {
    throw new Error("Outlook could not save the draft (HTTP " + response.status +
      "). Check Drafts before trying again. You may need to sign in again.");
  }
  let draft;
  try { draft = await response.json(); }
  catch { throw new Error("Outlook returned an incomplete response. Check Drafts before trying again."); }
  if (draft.isDraft !== true || typeof draft.id !== "string" || !draft.id) {
    throw new Error("Outlook did not confirm a draft. Check your Drafts folder before trying again.");
  }
  return { id: draft.id, webLink: outlookLink(draft.webLink) };
}
