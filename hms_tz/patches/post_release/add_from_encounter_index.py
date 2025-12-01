import frappe


def execute():
    """Ensure index on from_encounter to speed up admission validation lookups."""
    frappe.db.add_index("Patient Encounter", ["from_encounter"], index_name="from_encounter")
