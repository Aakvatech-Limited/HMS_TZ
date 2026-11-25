from hms_tz.hms_tz.setup_screens.healthcare_template import ITEM_GROUP_FILTERS, HealthcareTemplate


class ClinicalProcedureTemplate(HealthcareTemplate):
	"""Setup screen of the Clinical Procedure Templates.

	The template name names both the template and its Item, so it is fixed once the template exists and
	import matches templates by it. The consumables table stays on the desk form.
	"""

	doctype = "Clinical Procedure Template"
	label = "procedure template"
	plural_label = "procedure templates"
	extra_fields = {
		"template": {"set_only_once": 1},
		"item_group": {"link_filters": ITEM_GROUP_FILTERS},
		"medical_department": {},
		"is_inpatient": {},
		"is_billable": {},
		"rate": {},
		"disabled": {},
	}
	match_field = "template"
	list_filters = ("template", "item_group", "medical_department", "is_inpatient", "disabled")
