from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class JubileeUpdate(CompanyRecords):
	"""Read-only setup screen of the company's Jubilee Updates: what each Jubilee price package download changed.

	The price package download creates them, so they are only viewed here; viewing one shows its changed
	price package rows.
	"""

	doctype = "Jubilee Update"
	label = "Jubilee update"
	plural_label = "Jubilee updates"
	extra_fields = {"timestamp": {}, "current_log": {}, "previous_log": {}, "user_id": {}}
	has_setup_step = False
	has_add_actions = False
	is_read_only = True
	order_by = "timestamp desc"
	child_table = "price_package"
	child_fields = (
		"change_type",
		"service_type",
		"service_name",
		"itemcode",
		"itemname",
		"itemprice",
		"fields_changed",
	)
