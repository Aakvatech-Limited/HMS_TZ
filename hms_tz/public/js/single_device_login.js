// Single-device login: when this user logs in elsewhere, the server clears
// old sessions and publishes hms_tz_sessions_cleared to the user's room.
// Every connected tab then checks its own session; the ones that were
// killed get a session-expired response and are sent to the login page
// immediately, instead of waiting for the user's next click.
//
// Registered on app_ready because frappe.realtime.on() silently drops
// listeners added before frappe.realtime.init() creates the socket, and
// app bundles execute before desk startup.
$(document).on("app_ready", () => {
  frappe.realtime.on("hms_tz_sessions_cleared", () => {
    fetch("/api/method/frappe.auth.get_logged_user", {
      headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
    })
      .then((response) => {
        if (response.status === 403 || response.status === 401) {
          window.location.replace("/login?redirect-to=/app");
        }
      })
      .catch(() => window.location.replace("/login?redirect-to=/app"));
  });
});
