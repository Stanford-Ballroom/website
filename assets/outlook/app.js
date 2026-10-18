import { PublicClientApplication } from "@azure/msal-browser";
import { GRAPH_SCOPES } from "./drafts.js";
import { mountComposer } from "./view.js";

async function makeAuth(config) {
  const app = new PublicClientApplication(config);
  await app.initialize();
  let account;
  return {
    async login() {
      const result = await app.loginPopup({ scopes: [...GRAPH_SCOPES], prompt: "select_account" });
      account = result.account;
      app.setActiveAccount(account);
      return account.username;
    },
    async token() {
      const result = await app.acquireTokenSilent({ scopes: [...GRAPH_SCOPES], account });
      return result.accessToken;
    },
    async clear() {
      await app.clearCache({ account });
      account = undefined;
    }
  };
}

mountComposer(document, window, { makeAuth }).catch(() => {
  document.getElementById("status").textContent = "Could not start the draft composer. Refresh the page to try again.";
});
