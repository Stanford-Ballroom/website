import { announcementText } from "./whatsapp-format.js";

export function showWhatsAppView(doc = document, win = window) {
  const url = new URL(win.location.href);
  if (url.searchParams.get("format") !== "whatsapp") return false;
  const source = doc.getElementById("email-announcement");
  const title = doc.querySelector(".email-title");
  if (!source || !title) return false;
  const text = announcementText(title.textContent, source, doc.querySelector('link[rel="canonical"]')?.href);
  const element = (tag, content, parent) => {
    const node = doc.createElement(tag);
    if (content) node.textContent = content;
    if (parent) parent.append(node);
    return node;
  };

  const style = element("style");
  style.textContent = `
    body.whatsapp-view { margin:0; padding:24px 16px; background:#f2f1ee; color:#242421; font:17px/1.5 Arial,Helvetica,sans-serif; }
    .whatsapp-view main { box-sizing:border-box; max-width:800px; margin:0 auto; padding:24px; background:#fff; border-top:4px solid #8c1515; border-radius:4px; }
    .whatsapp-view h1 { margin:12px 0 8px; font-size:28px; line-height:1.25; }
    .whatsapp-view p { margin:0 0 20px; }
    .whatsapp-view a { color:#8c1515; }
    .whatsapp-view label { display:block; font-weight:bold; margin-bottom:8px; }
    .whatsapp-view textarea { box-sizing:border-box; display:block; width:100%; height:60vh; min-height:320px; resize:vertical; padding:14px; border:1px solid #aaa; border-radius:4px; font:16px/1.6 ui-monospace,monospace; background:#fff; color:#242421; }
    .whatsapp-view button { margin-top:16px; padding:12px 18px; border:0; border-radius:4px; background:#8c1515; color:#fff; font:inherit; cursor:pointer; }
    .whatsapp-view button:disabled { opacity:.65; cursor:wait; }
    .whatsapp-view :focus-visible { outline:3px solid #a65f00; outline-offset:3px; }
    .whatsapp-view [role=status] { margin:12px 0 0; min-height:1.5em; }
    @media(max-width:600px) { body.whatsapp-view { padding:12px 8px; } .whatsapp-view main { padding:16px; } }
    @media(prefers-color-scheme:dark) { body.whatsapp-view { background:#141619; color:#eeeeef; } .whatsapp-view main { background:#202327; } .whatsapp-view textarea { background:#141619; color:#eeeeef; border-color:#73777c; } .whatsapp-view a { color:#ffb5b5; } }
  `;
  doc.head.append(style);
  const main = element("main");
  const back = element("a", "← View email", main);
  url.searchParams.delete("format");
  back.href = url.href;
  element("h1", "Copy for WhatsApp", main);
  element("p", "Shorten or edit the announcement, then copy and paste it into your group. Changes stay in this tab and are lost when you leave or reload.", main);
  const label = element("label", "Message", main);
  label.htmlFor = "whatsapp-message";
  const textarea = element("textarea", null, main);
  textarea.id = "whatsapp-message";
  textarea.value = text;
  textarea.spellcheck = false;
  const button = element("button", "Copy for WhatsApp", main);
  button.type = "button";
  const status = element("p", null, main);
  status.setAttribute("role", "status");
  textarea.addEventListener("input", () => { status.textContent = ""; });
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      if (!win.navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await win.navigator.clipboard.writeText(textarea.value);
      status.textContent = "Copied! Paste into WhatsApp to see the formatting.";
    } catch {
      textarea.focus();
      textarea.select();
      status.textContent = "Text selected. Press ⌘C / Ctrl+C, or use your device’s Copy command.";
    } finally {
      button.disabled = false;
    }
  });
  doc.title = `${title.textContent} — WhatsApp`;
  doc.body.className = "whatsapp-view";
  doc.body.removeAttribute("style");
  doc.body.replaceChildren(main);
  return true;
}

if (typeof document !== "undefined" && typeof window !== "undefined") showWhatsAppView();
