import { broadcastResponseToMainFrame } from "@azure/msal-browser/redirect-bridge";

broadcastResponseToMainFrame().catch(() => {
  document.getElementById("auth-status").textContent =
    "Microsoft sign-in could not return to the composer. Close this window and try signing in again.";
});
