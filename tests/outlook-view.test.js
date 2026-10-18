import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { parseHTML } from "linkedom";
import { mountComposer } from "../assets/outlook/view.js";

const ID = "11111111-2222-3333-4444-555555555555";
const PAYLOAD = { schemaVersion: 1, subject: "Week 5", html: "<!doctype html><html><head><style>p{color:red}</style></head><body>Friday, 6–9 pm</body></html>" };
const tick = () => new Promise(resolve => setImmediate(resolve));

function fixture(configured = true) {
  const settings = { clientId: configured ? ID : "", tenantId: configured ? ID : "",
    redirectUri: "/preview/outlook/auth.html", recipient: "list@example.edu", issues: [
      { id: "fall26/week5", url: "/preview/outlook/issues/fall26/week5.json" },
      { id: "fall26/week4", url: "/preview/outlook/issues/fall26/week4.json" }
    ] };
  const { document } = parseHTML('<html><body><script id="outlook-settings" type="application/json"></script>' +
    '<form id="draft-form"><select id="issue"><option value="fall26/week5">Week 5</option><option value="fall26/week4">Week 4</option></select>' +
    '<input id="subject"><input id="recipient"><button id="sign-in"></button><button id="disconnect"></button><button id="create-draft"></button></form>' +
    '<a id="open-draft" hidden></a><p id="status"></p><p id="account"></p><iframe id="preview" sandbox=""></iframe>' +
    '<details id="setup"><form id="configuration"><input id="client-id"><input id="tenant-id"><button id="save-config"></button></form></details></body></html>');
  document.getElementById("outlook-settings").textContent = JSON.stringify(settings);
  // LinkeDOM exposes a getter-only select.value; add the browser's setter for interaction tests.
  const select = document.getElementById("issue");
  Object.defineProperty(select, "value", { writable: true, value: "fall26/week5" });
  const values = new Map();
  const win = { location: new URL("https://example.edu/preview/outlook/?issue=fall26/week5"), localStorage: {
    getItem: key => values.get(key), setItem: (key, value) => values.set(key, value)
  } };
  const el = id => document.getElementById(id);
  const emit = (id, type) => el(id).dispatchEvent(new document.defaultView.Event(type, { cancelable: true }));
  return { document, win, el, emit, values };
}

test("explicit sign-in and submit are required; a double submit saves one exact HTML draft", async () => {
  const f = fixture();
  let logins = 0, writes = 0, release, posted;
  await mountComposer(f.document, f.win, {
    makeAuth: async () => ({ login: async () => { logins++; return "me@example.edu"; }, token: async () => "token", clear: async () => {} }),
    fetchImpl: async (url, options) => {
      if (options.method !== "POST") return { ok: true, json: async () => PAYLOAD };
      writes++;
      posted = JSON.parse(options.body);
      return new Promise(resolve => { release = () => resolve({ ok: true, json: async () => ({
        isDraft: true, id: "draft-id", webLink: "https://outlook.office.com/mail/draft-id"
      }) }); });
    }
  });
  assert.equal(logins, 0);
  assert.equal(writes, 0);
  assert.equal(f.el("create-draft").disabled, true);
  assert.equal(f.el("preview").srcdoc, PAYLOAD.html);
  f.emit("draft-form", "submit");
  await tick();
  assert.equal(writes, 0);
  f.emit("sign-in", "click");
  await tick();
  f.el("subject").value = "Edited week 5";
  f.el("recipient").value = "test@example.edu";
  f.emit("draft-form", "submit");
  f.emit("draft-form", "submit");
  await tick();
  assert.equal(writes, 1);
  assert.equal(posted.subject, "Edited week 5");
  assert.equal(posted.body.content, PAYLOAD.html);
  assert.equal(posted.toRecipients[0].emailAddress.address, "test@example.edu");
  release(); await tick();
  assert.equal(f.el("open-draft").hidden, false);
  assert.equal(f.el("create-draft").disabled, true);
  f.emit("draft-form", "submit"); await tick();
  assert.equal(writes, 1);
  const saved = JSON.parse(f.values.get("ballroom-outlook-config"));
  assert.deepEqual(Object.keys(saved).sort(), ["clientId", "tenantId"]);
});

test("without app IDs the preview works and Microsoft sign-in stays disabled", async () => {
  const f = fixture(false);
  await mountComposer(f.document, f.win, { makeAuth: () => { throw new Error("Must not authenticate"); },
    fetchImpl: async () => ({ ok: true, json: async () => PAYLOAD }) });
  assert.equal(f.el("setup").open, true);
  assert.equal(f.el("sign-in").disabled, true);
  assert.equal(f.el("create-draft").disabled, true);
  assert.equal(f.el("subject").value, "Week 5");
});

test("a delayed issue response cannot replace the latest selected announcement", async () => {
  const f = fixture(false);
  let releaseOld;
  const mounting = mountComposer(f.document, f.win, { makeAuth: async () => {}, fetchImpl: async url => {
    if (url.endsWith("week5.json")) return new Promise(resolve => { releaseOld = () => resolve({ ok: true, json: async () => PAYLOAD }); });
    return { ok: true, json: async () => ({ ...PAYLOAD, subject: "Week 4" }) };
  } });
  await tick();
  f.el("issue").value = "fall26/week4"; f.emit("issue", "change"); await tick();
  releaseOld(); await mounting;
  assert.equal(f.el("subject").value, "Week 4");
});

test("a failed draft request shows a useful status and allows a deliberate retry", async () => {
  const f = fixture();
  let writes = 0;
  await mountComposer(f.document, f.win, {
    makeAuth: async () => ({ login: async () => "me@example.edu", token: async () => "token", clear: async () => {} }),
    fetchImpl: async (url, options) => options.method === "POST" ? (writes++, { ok: false, status: 429 }) : { ok: true, json: async () => PAYLOAD }
  });
  f.emit("sign-in", "click"); await tick();
  f.emit("draft-form", "submit"); await tick();
  assert.equal(writes, 1);
  assert.match(f.el("status").textContent, /Check Drafts before trying again/);
  assert.equal(f.el("create-draft").disabled, false);
  assert.equal(f.el("open-draft").hidden, true);
});

test("built composer has working callback, bundles, and same-prefix issue payloads", { skip: !process.env.EMAIL_TEST_SITE }, () => {
  const root = process.env.EMAIL_TEST_SITE;
  const { document } = parseHTML(readFileSync(path.join(root, "outlook/index.html"), "utf8"));
  const settings = JSON.parse(document.getElementById("outlook-settings").textContent);
  const prefix = settings.redirectUri.replace(/outlook\/auth\.html$/, "");
  assert.ok(settings.issues.length > 0);
  const local = url => path.join(root, decodeURI(url.replace(prefix, "")));
  assert.ok(existsSync(local(settings.redirectUri)));
  assert.ok(existsSync(path.join(root, "outlook/setup/index.html")));
  assert.equal(document.getElementById("preview").getAttribute("sandbox"), "");
  for (const issue of settings.issues) {
    assert.ok(issue.url.startsWith(prefix + "outlook/issues/"), issue.url);
    assert.equal(JSON.parse(readFileSync(local(issue.url), "utf8")).schemaVersion, 1);
    assert.ok(!issue.id.startsWith("/"));
  }
  for (const script of document.querySelectorAll("script[src]")) assert.ok(existsSync(local(script.getAttribute("src"))));
  const { document: auth } = parseHTML(readFileSync(local(settings.redirectUri), "utf8"));
  assert.equal(auth.querySelectorAll("script[src]").length, 1);
  assert.ok(existsSync(local(auth.querySelector("script[src]").getAttribute("src"))));
});
