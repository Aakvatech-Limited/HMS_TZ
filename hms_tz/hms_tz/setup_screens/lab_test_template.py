from hms_tz.hms_tz.setup_screens.healthcare_template import ITEM_GROUP_FILTERS, HealthcareTemplate


class LabTestTemplate(HealthcareTemplate):
	"""Setup screen of the Lab Test Templates.

	Users complete templates here, often by importing the result format, ranges and component rows. The lab
	test code names the template and its Item, so it is fixed once the template exists.
	"""

	doctype = "Lab Test Template"
	label = "lab template"
	plural_label = "lab templates"
	extra_fields = {
		"lab_test_code": {"set_only_once": 1},
		"lab_test_group": {"link_filters": ITEM_GROUP_FILTERS},
		"disabled": {},
		"lab_test_template_type": {},
		"is_billable": {},
		"lab_test_rate": {},
		"lab_test_uom": {},
		"lab_test_normal_range": {},
		"sample": {},
	}
	import_tables = {
		"normal_test_templates": [
			"lab_test_event",
			"allow_blank",
			"lab_test_uom",
			"secondary_uom",
			"conversion_factor",
			"normal_range",
		],
		"descriptive_test_templates": ["particulars", "result_component", "allow_blank"],
		"lab_test_groups": [
			"template_or_new_line",
			"lab_test_template",
			"lab_test_rate",
			"lab_test_description",
			"group_event",
			"group_test_uom",
			"secondary_uom",
			"conversion_factor",
			"allow_blank",
			"group_test_normal_range",
		],
	}
	match_field = "lab_test_code"
	list_filters = ("lab_test_name", "lab_test_group", "department", "lab_test_template_type", "disabled")
