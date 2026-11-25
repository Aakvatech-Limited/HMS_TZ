from hms_tz.hms_tz.setup_screens.healthcare_template import ITEM_GROUP_FILTERS, HealthcareTemplate


class RadiologyExaminationTemplate(HealthcareTemplate):
	"""Setup screen of the Radiology Examination Templates.

	The procedure name names the template and the item code names its Item, so both are fixed once the
	template exists. Import matches templates by item code.
	"""

	doctype = "Radiology Examination Template"
	label = "radiology template"
	plural_label = "radiology templates"
	extra_fields = {
		"procedure_name": {"set_only_once": 1},
		"item_code": {"set_only_once": 1},
		"item_group": {"link_filters": ITEM_GROUP_FILTERS},
		"modality_type": {},
		"body_part": {},
		"is_billable": {},
		"rate": {},
		"disabled": {},
	}
	match_field = "item_code"
	list_filters = ("procedure_name", "modality_type", "medical_department", "disabled")
