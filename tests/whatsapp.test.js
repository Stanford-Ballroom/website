import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { test } from "node:test";
import { parseHTML } from "linkedom";
import { announcementText } from "../assets/emails/whatsapp-format.js";
import { showWhatsAppView } from "../assets/emails/whatsapp-view.js";

function page(body = "<p>Hello <strong>dancers</strong>!</p>") {
  return parseHTML(`<!doctype html><html><head><link rel="canonical" href="https://stanfordballroom.com/emails/fall26/week1.html"></head>
    <body class="email-bg" style="padding:0;background:white"><p>Summary and logo</p><h1 class="email-title">Welcome!</h1>
    <div id="email-announcement">${body}</div><footer>Mailing list settings</footer></body></html>`).document;
}
function convert(body) {
  return announcementText("Welcome!", page(body).getElementById("email-announcement"), "");
}
function windowAt(query = "?format=whatsapp", clipboard) {
  return { location: { href: `https://example.test/preview/emails/fall26/week1.html${query}` }, navigator: { clipboard } };
}

test("headings, nested emphasis, links, quotes, and code retain WhatsApp markers", () => {
  const result = convert('<h2>First <strong>class</strong></h2><p><strong>Welcome <em>back</em></strong>, <del>old time</del>!</p><p><a href="https://example.test/schedule">Schedule</a> · <a href="mailto:hello@example.test">hello@example.test</a></p><blockquote><p>See you Monday.</p></blockquote><pre><code>a  b\nc</code></pre>');
  assert.equal(result, '*Welcome!*\n\n*First class*\n\n*Welcome _back_*, ~old time~!\n\nSchedule: https://example.test/schedule · hello@example.test\n\n> See you Monday.\n\n```\na  b\nc\n```\n');
});

test("lists keep separate items, nested structure, paragraphs, and ordered starts", () => {
  const result = convert('<ul><li>First</li><li><p>Second</p><p>More detail.</p><ul><li>Nested</li></ul></li></ul><ol start="3"><li>Third</li><li value="7">Seventh</li></ol>');
  assert.match(result, /- First\n- Second\n\n  More detail\.\n\n  - Nested/);
  assert.match(result, /3\. Third\n7\. Seventh/);
});

test("layout tables preserve notices and button links, without image URLs", () => {
  const result = convert('<table role="presentation"><tr><td><p style="font-weight:bold">New here?</p><p>Welcome!</p><table role="presentation"><tr><td><a href="https://example.test/join" style="font-weight:700">Join us</a></td></tr></table><img alt="Poster" src="https://example.test/poster.jpg"><p>Photo caption</p></td></tr></table><p hidden>Hidden</p><script>bad()</script>');
  assert.match(result, /\*New here\?\*/);
  assert.match(result, /\*Join us\*: https:\/\/example.test\/join/);
  assert.match(result, /Photo caption/);
  assert.doesNotMatch(result, /poster.jpg|Hidden|bad\(\)/);
});

test("single-track schedules retain instructor and each time slot", () => {
  const result = convert('<table><caption>Lesson schedule</caption><thead><tr><th>Time</th><th>Class<br><span>by ‘Ikaika</span></th></tr></thead><tbody><tr><th>7:30 – 8:30 pm</th><td>Beginner</td></tr><tr><th>8:30 – 9:30 pm</th><td>Intermediate</td></tr></tbody></table>');
  assert.match(result, /\*Lesson schedule\*\nClass by ‘Ikaika\n- 7:30 – 8:30 pm — Beginner\n- 8:30 – 9:30 pm — Intermediate/);
});

test("multi-track schedules associate headers with classes and shared rows", () => {
  const result = convert('<table><thead><tr><th>Time</th><th>Standard<br>by ‘Ikaika</th><th>Latin<br>by Stacey</th></tr></thead><tbody><tr><th>7 pm</th><td>Beginner</td><td>Intermediate</td></tr><tr><th>9 pm</th><td colspan="2">Practice and <strong>social</strong></td></tr></tbody></table>');
  assert.match(result, /- 7 pm — Standard by ‘Ikaika: Beginner — Latin by Stacey: Intermediate/);
  assert.match(result, /- 9 pm — Practice and \*social\*/);
});

test("image links keep their destination and caption as the label", () => {
  assert.match(convert('<p><a href="https://example.test/event"><img src="https://example.test/poster.png" alt="Event details"></a></p>'), /Event details: https:\/\/example.test\/event/);
});

test("ordinary email and unrelated query parameters leave the document untouched", () => {
  for (const query of ["", "?format=email", "?utm_source=whatsapp"]) {
    const doc = page();
    const before = doc.toString();
    assert.equal(showWhatsAppView(doc, windowAt(query)), false);
    assert.equal(doc.toString(), before);
  }
});

test("query view removes email chrome and copies the edited message", async () => {
  const doc = page();
  let copied;
  const win = windowAt("?utm_source=test&format=whatsapp#first", { writeText: async value => { copied = value; } });
  assert.equal(showWhatsAppView(doc, win), true);
  const field = doc.querySelector("textarea");
  assert.match(field.value, /^\*Welcome!\*\n\nHello \*dancers\*!/);
  assert.match(field.value, /Full announcement: https:\/\/stanfordballroom.com\/emails\/fall26\/week1.html/);
  assert.doesNotMatch(field.value, /Summary and logo|Mailing list/);
  assert.equal(doc.body.hasAttribute("style"), false);
  assert.equal(doc.querySelector("a").href, "https://example.test/preview/emails/fall26/week1.html?utm_source=test#first");
  field.value = "*My shorter message*";
  doc.querySelector("button").click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(copied, "*My shorter message*");
  assert.match(doc.querySelector('[role="status"]').textContent, /^Copied!/);
  assert.equal(doc.querySelector("button").disabled, false);
  field.dispatchEvent(new doc.defaultView.Event("input"));
  assert.equal(doc.querySelector('[role="status"]').textContent, "");
});

test("blocked or unavailable clipboard selects text for manual copying", async () => {
  for (const clipboard of [undefined, { writeText: async () => { throw new Error("Denied"); } }]) {
    const doc = page();
    showWhatsAppView(doc, windowAt("?format=whatsapp", clipboard));
    let selected = false;
    doc.querySelector("textarea").select = () => { selected = true; };
    doc.querySelector("button").click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(selected, true);
    assert.match(doc.querySelector('[role="status"]').textContent, /Text selected/);
    assert.equal(doc.querySelector("button").disabled, false);
  }
});

test("conversion treats announcement text as text, including HTML-looking literals", () => {
  const doc = page('<p>&lt;img src=x onerror=alert(1)&gt; &amp; friends</p>');
  showWhatsAppView(doc, windowAt());
  assert.match(doc.querySelector("textarea").value, /<img src=x onerror=alert\(1\)> & friends/);
  assert.equal(doc.querySelectorAll("img").length, 0);
});

test("built and minified Hugo assets work on all five real announcements", { skip: !process.env.EMAIL_TEST_SITE }, () => {
  for (const issue of ["fall26/week1", "spring26/week1", "spring26/week6", "spring26/week9", "spring26/week10"]) {
    const html = readFileSync(path.join(process.env.EMAIL_TEST_SITE, "emails", `${issue}.html`), "utf8");
    const doc = parseHTML(html).document;
    const script = doc.querySelector("script[data-email-browser]");
    assert.ok(script, `${issue}: browser helper missing`);
    const js = readFileSync(path.join(process.env.EMAIL_TEST_SITE, "emails", path.basename(script.src)), "utf8");
    vm.runInNewContext(js, { document: doc, window: windowAt(), URL });
    const text = doc.querySelector("textarea").value;
    assert.ok(text.length > 300, `${issue}: missing content`);
    assert.doesNotMatch(text, /<table|<p>|HAHAHUGOSHORTCODE|Mailing list settings|Text%20on%20Side/);
    assert.match(text, new RegExp(`Full announcement: https://stanfordballroom.com/emails/${issue}\\.html`));
    if (issue === "fall26/week1") {
      assert.match(text, /‘Ikaika/);
      assert.match(text, /- 7:30 – 8:30 pm — Beginner/);
      assert.match(text, /- 8:30 – 9:30 pm — Intermediate/);
      assert.match(text, /TREEFEST/);
      assert.match(text, /Mentored Practices/);
    }
  }
});
