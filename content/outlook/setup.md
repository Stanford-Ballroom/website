---
title: Connect Outlook
type: outlook
layout: setup
url: /outlook/setup/
outputs: [HTML]
---
Register a Microsoft application once, then sign in to create drafts from the email composer.

1. Open [Microsoft Entra app registrations](https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade) and choose **New registration**.
2. Name it **Stanford Ballroom Drafts**. For a Stanford-only application, choose **Accounts in this organizational directory only**.
3. Add the callback shown above as a **Single-page application (SPA)** redirect URI. The production callback is **https://ballroom.stanford.edu/outlook/auth.html**. When testing a PR preview, register its callback too.
4. Under **API permissions**, add **Microsoft Graph → Delegated permissions → Mail.ReadWrite**. Remove the default User.Read permission if present. Leave implicit access-token and ID-token grants disabled.
5. From the app's Overview, copy the **Application (client) ID** and **Directory (tenant) ID** into the composer's **Microsoft connection setup**, then save.
6. Choose the announcement, sign in with your Stanford mailbox, review the subject and recipient, and select **Create Outlook draft**. Open the saved draft in Outlook to review it.

Microsoft requires Mail.ReadWrite for creating drafts. This permission covers reading and writing mailbox items; this composer uses it only to create a draft. It requests no Mail.Send permission and has no send action.

Sign-in uses Microsoft's MSAL library and authorization code flow with PKCE. The application has no client secret. App IDs can be remembered in your browser; authentication tokens stay in the tab's memory and are cleared on reload or Disconnect.

If Stanford requires administrator consent or restricts app registrations, ask the Microsoft 365 administrator to register or approve this app.

The HTML comes directly from the existing script-free email build. Inline styles, the preheader, Outlook conditional markup, dark-mode CSS, links, and image URLs are preserved in the submitted HTML. Review the result in Outlook because Microsoft may normalize HTML when storing or editing a message.
