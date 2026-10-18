import assert from "node:assert/strict";
import { test } from "node:test";
import { applicationConfig, messageFor, loadAnnouncement, createHtmlDraft, outlookLink,
  GRAPH_SCOPES, DRAFT_ENDPOINT } from "../assets/outlook/drafts.js";

const ID = "11111111-2222-3333-4444-555555555555";
const HTML = '<!doctype html><html><head><style>@media(prefers-color-scheme:dark){.logo{color:white}}</style></head><body><p>Friday practice, 6–9 pm</p><!--[if mso]><table role="presentation"><tr><td><![endif]--><p>Hello!</p><!--[if mso]></td></tr></table><![endif]--></body></html>';
const PAYLOAD = { schemaVersion: 1, subject: "Week 5", html: HTML };
const LINK = "https://outlook.office.com/mail/deeplink/compose/item-id";

test("draft body preserves the full HTML and recipient edits", () => {
  const message = messageFor(PAYLOAD, " Edited subject ", "list@example.edu, me@example.edu");
  assert.deepEqual(message, { subject: "Edited subject", body: { contentType: "HTML", content: HTML },
    toRecipients: ["list@example.edu", "me@example.edu"].map(address => ({ emailAddress: { address } })) });
});

test("only Mail.ReadWrite is requested and tokens use memory storage", () => {
  assert.deepEqual(GRAPH_SCOPES, ["Mail.ReadWrite"]);
  const config = applicationConfig(ID, ID, "/preview/outlook/auth.html", "https://example.edu");
  assert.equal(config.auth.redirectUri, "https://example.edu/preview/outlook/auth.html");
  assert.equal(config.cache.cacheLocation, "memoryStorage");
  for (const redirect of ["https://other.test/auth", "/auth#token", "/auth?next=elsewhere"]) {
    assert.throws(() => applicationConfig(ID, ID, redirect, "https://example.edu"));
  }
  assert.throws(() => applicationConfig("bad", ID, "/auth", "https://example.edu"));
});

test("invalid subjects, recipients, and browser exports fail before a write", () => {
  for (const subject of ["", "hello\r\nBcc: someone@example.edu"]) {
    assert.throws(() => messageFor(PAYLOAD, subject, "list@example.edu"));
  }
  for (const recipient of ["", "Display Name <list@example.edu>", "list@example.edu\nother@example.edu"]) {
    assert.throws(() => messageFor(PAYLOAD, "Week 5", recipient));
  }
  for (const html of ["<p>fragment</p>", HTML.replace("<body>", '<body onload="bad()">'),
    HTML.replace("</head>", "<script src='/helper.js'></script></head>")]) {
    assert.throws(() => messageFor({ ...PAYLOAD, html }, "Week 5", "list@example.edu"));
  }
});

test("announcement loading stays on the website without redirects or credentials", async () => {
  let calls = 0;
  const fetchImpl = async (url, options) => {
    calls++;
    assert.equal(url, "https://example.edu/preview/outlook/issues/fall26/week5.json");
    assert.deepEqual(options, { redirect: "error", credentials: "omit" });
    return { ok: true, json: async () => PAYLOAD };
  };
  assert.equal(await loadAnnouncement("/preview/outlook/issues/fall26/week5.json", "https://example.edu", fetchImpl), PAYLOAD);
  await assert.rejects(loadAnnouncement("https://other.test/email.json", "https://example.edu", fetchImpl));
  assert.equal(calls, 1);
});

test("creation makes one POST to the draft endpoint and verifies Outlook's response", async () => {
  const message = messageFor(PAYLOAD, "Week 5", "list@example.edu");
  let calls = 0;
  const result = await createHtmlDraft("test-token", message, async (url, options) => {
    calls++;
    assert.equal(url, DRAFT_ENDPOINT);
    assert.equal(url, "https://graph.microsoft.com/v1.0/me/messages");
    assert.equal(options.method, "POST");
    assert.equal(options.headers.Authorization, "Bearer test-token");
    assert.equal(options.redirect, "error");
    assert.deepEqual(JSON.parse(options.body), message);
    return { ok: true, json: async () => ({ id: "item-id", isDraft: true, webLink: LINK }) };
  });
  assert.equal(calls, 1);
  assert.deepEqual(result, { id: "item-id", webLink: LINK });
});

test("ambiguous responses and throttling never automatically repeat the POST", async () => {
  for (const response of [new Error("offline"), { ok: false, status: 429 }, { ok: false, status: 500 },
    { ok: true, json: async () => { throw new SyntaxError(); } },
    { ok: true, json: async () => ({ id: "item-id", isDraft: false, webLink: LINK }) }]) {
    let calls = 0;
    await assert.rejects(createHtmlDraft("token", {}, async () => {
      calls++;
      if (response instanceof Error) throw response;
      return response;
    }), /[Cc]heck.*Drafts|[Cc]heck.*draft/);
    assert.equal(calls, 1);
  }
  for (const url of ["javascript:alert(1)", "http://outlook.office.com/mail/1", "https://outlook.office.com.evil.test/mail/1"]) {
    assert.throws(() => outlookLink(url));
  }
});
