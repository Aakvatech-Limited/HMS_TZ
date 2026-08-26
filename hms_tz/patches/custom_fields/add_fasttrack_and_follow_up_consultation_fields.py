import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	frappe.reload_doc("healthcare", "doctype", "appointment_type", force=True)
	frappe.reload_doc("hms_tz", "doctype", "patient_appointment", force=True)

	type_fields = get_fields()
	create_custom_fields(type_fields, update=True)

	update_has_cons_value()
	removed_type_custom_field()

	appointment_fields = get_fields(for_appointment=True)
	create_custom_fields(appointment_fields, update=True)
	frappe.reload_doc("healthcare", "doctype", "appointment_type", force=True)
	frappe.reload_doc("hms_tz", "doctype", "patient_appointment", force=True)


def get_fields(for_appointment=False):
	fields = {}
	if for_appointment:
		fields["Patient Appointment"] = [
			{
				"fieldname": "apply_fasttrack_charge",
				"fieldtype": "Check",
				"label": "Apply Fasttrack Charge",
				"insert_after": "column_break_49",
				"default": 1,
				"description": "If checked, Fasttrack Charges will be applied for this appointment",
			}
		]

	else:
		fields["Appointment Type"] = [
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
				"fieldname": "has_no_consultation_charges_for_cash",
				"fieldtype": "Check",
				"label": "Has No Consultation Charge for Cash",
				"insert_after": "source",
				"description": "If checked, Consultation Charges will not be applied for cash appointments",
			},
			{
				"fieldname": "has_no_consultation_charges_for_insurance",
				"fieldtype": "Check",
				"label": "Has No Consultation Charge for Insurance",
				"insert_after": "has_no_consultation_charges_for_cash",
				"description": "If checked, Consultation Charges will not be applied for Insurance appointments",
			},
			{
				"fieldname": "visit_type_id",
				"label": "Visit Type ID",
				"fieldtype": "Select",
				"insert_after": "has_no_consultation_charges_for_insurance",
				"translatable": 1,
				"options": """\n1-Normal Visit\n2-Emergency Visit\n3-Referral Visit\n4-Vifurushi Follow up Visit\n5-Investigation Visit\n6-Occupational Visit\n7-Medicine Re-fill Visit\n8-Other Visit\n9-Follow up Visit\n10-New case Visit""",
			},
			{
				"fieldname": "followup_cb",
				"fieldtype": "Column Break",
				"insert_after": "visit_type_id",
			},
			{
				"fieldname": "assistant_md_followup_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "Assistant Medical Officer Followup Item",
				"insert_after": "followup_cb",
			},
			{
				"fieldname": "gp_followup_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "GP Followup Item",
				"insert_after": "assistant_md_followup_item",
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
				"fieldname": "assistant_md_fasttrack_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "Assistant Medical Officer Fasttrack Item",
				"insert_after": "fasttrack_cb",
			},
			{
				"fieldname": "gp_fasttrack_item",
				"fieldtype": "Link",
				"options": "Item",
				"label": "GP Fasttrack Item",
				"insert_after": "assistant_md_fasttrack_item",
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
		]

	return fields


def removed_type_custom_field():
	fields = [
		{
			"Appointment Type": [
				"follow_up_item",
				"has_no_consultation_charges",
			],
		},
		{
			"Patient Appointment": ["apply_fasttrack_charge"],
		},
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


def update_has_cons_value():
	# Guard: on fresh installs, the old custom field may not exist
	if not frappe.db.has_column("Appointment Type", "has_no_consultation_charges"):
		return

	app_type = frappe.query_builder.DocType("Appointment Type")
	(
		frappe.qb.update(app_type)
		.set(app_type.has_no_consultation_charges_for_insurance, 1)
		.where(app_type.has_no_consultation_charges == 1)
	).run()
