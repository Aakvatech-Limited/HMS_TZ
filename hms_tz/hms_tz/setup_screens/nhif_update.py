from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class NHIFUpdate(CompanyRecords):
	"""Read-only setup screen of the company's NHIF Updates: what each NHIF price package download changed.

	The price package download creates them, so they are only viewed here; viewing one shows its changed
	price package rows.
	"""

	doctype = "NHIF Update"
	label = "NHIF update"
	plural_label = "NHIF updates"
	extra_fields = {"user_id": {}}
	has_setup_step = False
	has_add_actions = False
	is_read_only = True
	order_by = "timestamp desc"
	child_table = "price_package"
	child_fields = (
		"service_type",
		"service_name",
		"itemcode",
		"itemname",
		"schemeid",
		"packageid",
		"unitprice",
		"fields_changed",
	)
