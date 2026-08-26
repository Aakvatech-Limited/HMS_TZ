import frappe
from frappe.permissions import get_doctypes_with_read


@frappe.whitelist()
def get_permitted_doctypes():
	"""Return doctypes the current user has read permission to, for search navigation.

	Uses Frappe's built-in permission check (get_doctypes_with_read) which
	respects Role Permissions and User Permissions for frappe.session.user.
	Child table (istable) doctypes are excluded since users don't navigate to them.
	"""
	permitted = get_doctypes_with_read()

	result = []
	for dt_name in permitted:
		try:
			meta = frappe.get_meta(dt_name)
		except Exception:
			continue

		# Skip child table doctypes — not directly navigable
		if meta.istable:
			continue

		slug = frappe.scrub(dt_name).replace("_", "-")
		description = dt_name if meta.issingle else f"{dt_name} List"

		result.append(
			{
				"label": dt_name,
				"description": description,
				"route": f"/app/{slug}",
				"type": "page",
			}
		)

	result.sort(key=lambda x: x["label"])
	return result
