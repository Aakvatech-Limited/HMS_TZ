from hms_tz.hms_tz.setup_screens.healthcare_template import ITEM_GROUP_FILTERS, HealthcareTemplate


class TherapyType(HealthcareTemplate):
	"""Setup screen of the Therapy Types.

	Each therapy type is its own record, even when an insurer bills many of them under one code. The therapy
	type names the record and the item code names its Item, so both are fixed once the record exists;
	import matches therapy types by item code. Exercises and body parts stay on the desk form.
	"""

	doctype = "Therapy Type"
	label = "therapy type"
	plural_label = "therapy types"
	extra_fields = {
		"therapy_type": {"set_only_once": 1},
		"item_code": {"set_only_once": 1},
		"item_group": {"link_filters": ITEM_GROUP_FILTERS},
		"default_duration": {},
		"description": {},
		"medical_department": {},
		"is_billable": {},
		"rate": {},
		"disabled": {},
	}
	match_field = "item_code"
	list_filters = ("therapy_type", "medical_department", "disabled")
