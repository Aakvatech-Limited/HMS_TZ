import frappe
from frappe.utils.telemetry import capture

no_cache = 1


def get_context():
	"""Boot data for the frappe-ui SPA. The template iterates `boot`."""
	if frappe.session.user != "Guest":
		capture("active_site", "frontend")

	return frappe._dict({"boot": get_boot()})


def get_boot():
	return frappe._dict(
		{
			"default_route": "/frontend",
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"csrf_token": frappe.sessions.get_csrf_token(),
		}
	)
