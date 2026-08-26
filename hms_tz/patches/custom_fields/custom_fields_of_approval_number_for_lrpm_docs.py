from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	doctypes = [
		"Lab Test",
		"Radiology Examination",
		"Clinical Procedure",
		"Delivery Note Item",
		"Original Delivery Note Item",
	]

	for doctype in doctypes:
		fields = get_custom_fields(doctype)
		create_custom_fields(fields, update=True)


def get_custom_fields(doctype):
	fields = {
		doctype: [
			{
				"fieldname": "approval_status",
				"label": "Approval Status",
				"fieldtype": "Data",
				"insert_after": "approval_type",
				"read_only": 1,
			},
			{
				"fieldname": "authorized_item_id",
				"label": "AuthorizedItemID",
				"fieldtype": "Data",
				"insert_after": "approval_status",
				"read_only": 1,
			},
			{
				"fieldname": "service_authorization_id",
				"label": "ServiceAuthorizationID",
				"fieldtype": "Data",
				"insert_after": "authorized_item_id",
				"read_only": 1,
			},
		],
	}
	return fields
