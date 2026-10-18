import { applicationConfig, messageFor, loadAnnouncement, createHtmlDraft } from "./drafts.js";

export async function mountComposer(doc, win, { makeAuth, fetchImpl = fetch }) {
  const settings = JSON.parse(doc.getElementById("outlook-settings").textContent);
  const element = id => doc.getElementById(id);
  const status = element("status");
  const issue = element("issue");
  const subject = element("subject");
  const recipient = element("recipient");
  const signIn = element("sign-in");
  const disconnect = element("disconnect");
  const save = element("create-draft");
  const open = element("open-draft");
  const clientId = element("client-id");
  const tenantId = element("tenant-id");
  let auth, signedIn = false, payload, busy = false, created = false, generation = 0;

  function update() {
    save.disabled = !signedIn || !payload || busy || created;
    signIn.disabled = !auth || busy;
    disconnect.hidden = !signedIn;
    issue.disabled = busy;
    subject.disabled = !payload || busy || created;
    recipient.disabled = !payload || busy || created;
    element("save-config").disabled = busy;
  }
  function say(message) { status.textContent = message; }
  function errorMessage(error) { return error?.message || "Something went wrong. Please try again."; }

  try {
    const saved = JSON.parse(win.localStorage.getItem("ballroom-outlook-config") || "{}");
    clientId.value = saved.clientId || settings.clientId || "";
    tenantId.value = saved.tenantId || settings.tenantId || "";
  } catch {
    clientId.value = settings.clientId || "";
    tenantId.value = settings.tenantId || "";
  }

  async function connect() {
    const config = applicationConfig(clientId.value.trim(), tenantId.value.trim(), settings.redirectUri, win.location.origin);
    if (auth) await auth.clear();
    signedIn = false;
    auth = await makeAuth(config);
    try {
      win.localStorage.setItem("ballroom-outlook-config", JSON.stringify({
        clientId: clientId.value.trim(), tenantId: tenantId.value.trim()
      }));
    } catch { /* App IDs can be entered again when browser storage is blocked. */ }
    element("setup").open = false;
    element("account").textContent = "Ready to sign in with Microsoft";
    update();
  }

  element("configuration").addEventListener("submit", async event => {
    event.preventDefault();
    busy = true; update();
    try { await connect(); say("Connection settings saved. Sign in with Microsoft to continue."); }
    catch (error) { say(errorMessage(error)); }
    finally { busy = false; update(); }
  });

  signIn.addEventListener("click", async () => {
    busy = true; update(); say("Complete sign-in in the Microsoft window.");
    try {
      const username = await auth.login();
      signedIn = true;
      element("account").textContent = "Signed in as " + username;
      say("Review the subject and recipient, then create your draft.");
    } catch (error) { say(errorMessage(error)); }
    finally { busy = false; update(); }
  });

  disconnect.addEventListener("click", async () => {
    busy = true; update();
    try {
      await auth.clear();
      signedIn = false;
      element("account").textContent = "Disconnected";
      say("Microsoft access for this tab has been cleared.");
    } catch (error) { say(errorMessage(error)); }
    finally { busy = false; update(); }
  });

  async function selectIssue() {
    const current = ++generation;
    payload = undefined; created = false; open.hidden = true;
    element("preview").removeAttribute("srcdoc");
    update();
    const choice = settings.issues.find(item => item.id === issue.value);
    if (!choice) { say("Choose an announcement to preview."); return; }
    say("Loading announcement…");
    try {
      const loaded = await loadAnnouncement(choice.url, win.location.origin, fetchImpl);
      messageFor(loaded, loaded.subject, settings.recipient);
      if (current !== generation) return;
      payload = loaded;
      subject.value = loaded.subject;
      recipient.value = settings.recipient;
      element("preview").srcdoc = loaded.html;
      say("Announcement ready. Review it before saving to Outlook.");
    } catch (error) { if (current === generation) say(errorMessage(error)); }
    finally { if (current === generation) update(); }
  }

  issue.addEventListener("change", selectIssue);
  element("draft-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (!signedIn || !payload || busy || created) return;
    let message;
    try { message = messageFor(payload, subject.value, recipient.value); }
    catch (error) { say(errorMessage(error)); return; }
    busy = true; update(); say("Saving the HTML email to your Outlook Drafts…");
    try {
      const token = await auth.token();
      const draft = await createHtmlDraft(token, message, fetchImpl);
      created = true;
      open.href = draft.webLink; open.hidden = false;
      say("Draft saved. Open it in Outlook to review and send when you're ready.");
    } catch (error) { say(errorMessage(error)); }
    finally { busy = false; update(); }
  });

  const requested = new URL(win.location.href).searchParams.get("issue");
  issue.value = settings.issues.find(item => item.id === requested)?.id || settings.issues[0]?.id || "";
  if (clientId.value && tenantId.value) {
    try { await connect(); }
    catch (error) { element("setup").open = true; say(errorMessage(error)); }
  } else {
    element("setup").open = true;
  }
  await selectIssue();
  update();
}
