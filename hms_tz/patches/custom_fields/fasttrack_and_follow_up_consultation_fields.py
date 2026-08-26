import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	removed_type_custom_field()

	fields = {
		"Patient Appointment": [
			{
				"fieldname": "apply_fasttrack_charge",
				"fieldtype": "Check",
				"label": "Apply Fasttrack Charge",
				"insert_after": "column_break_49",
				"default": 1,
			},
		],
		"Appointment Type": [
			{
				"fieldname": "source_sec",
				"fieldtype": "Section Break",
				"insert_after": "items",
			},
			{
				"fieldname": "source",
				"label": "Source",
				"fieldtype": "Data",
				"insert_after": "source_sec",
				"translatable": 1,
			},
			{
				"fieldname": "visit_type_id",
				"label": "Visit Type ID",
				"fieldtype": "Select",
				"insert_after": "source",
				"translatable": 1,
				"options": """\n1-Normal Visit\n2-Emergency Visit\n3-Referral Visit\n4-Vifurushi Follow up Visit\n5-Investigation Visit\n6-Occupational Visit\n7-Medicine Re-fill Visit\n8-Other Visit\n9-Follow up Visit\n10-New case Visit""",
			},
			{
				"fieldname": "followup_cb",
				"fieldtype": "Column Break",
				"insert_after": "visit_type_id",
			},
			{
				"fieldname": "gp_followup_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "GP Followup Item",
				"insert_after": "followup_cb",
			},
			{
				"fieldname": "specialist_followup_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "Specialist Followup Item",
				"insert_after": "gp_followup_item",
			},
			{
				"fieldname": "super_specialist_followup_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "Super Specialist Followup Item",
				"insert_after": "specialist_followup_item",
			},
			{
				"fieldname": "fasttrack_cb",
				"fieldtype": "Column Break",
				"insert_after": "super_specialist_followup_item",
			},
			{
				"fieldname": "gp_fasttrack_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "GP Fasttrack Item",
				"insert_after": "fasttrack_cb",
			},
			{
				"fieldname": "specialist_fasttrack_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "Specialist Fasttrack Item",
				"insert_after": "gp_fasttrack_item",
			},
			{
				"fieldname": "super_specialist_fasttrack_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "Super Specialist Fasttrack Item",
				"insert_after": "specialist_fasttrack_item",
			},
		],
	}

	create_custom_fields(fields, update=True)

	frappe.reload_doc("hms_tz", "doctype", "patient_appointment", force=True)


def removed_type_custom_field():
	fields = [
		{
			"Appointment Type": ["follow_up_item"],
		}
	]
	for row in fields:
		for key, value in row.items():
			for fieldname in value:
				custom_field = frappe.get_cached_value(
					"Custom Field", {"fieldname": fieldname, "dt": key}, "name"
				)
				if custom_field:
					frappe.delete_doc("Custom Field", custom_field)

	frappe.db.commit()
