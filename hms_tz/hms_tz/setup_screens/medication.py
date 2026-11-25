from hms_tz.hms_tz.setup_screens.healthcare_template import ITEM_GROUP_FILTERS, HealthcareTemplate


class Medication(HealthcareTemplate):
	"""Setup screen of the Medications, which include the consumables that doctors prescribe.

	The medication name names both the medication and its Item, so it is fixed once the medication exists and
	import matches medications by it. Interaction tables and prescription defaults stay on the desk form.
	"""

	doctype = "Medication"
	label = "medication"
	plural_label = "medications"
	extra_fields = {
		"medication_name": {"set_only_once": 1},
		"generic_name": {},
		"disabled": {},
		"strength_text": {},
		"item_group": {"link_filters": ITEM_GROUP_FILTERS},
		"is_billable": {},
		"rate": {},
		"default_dosage_form": {},
	}
	match_field = "medication_name"
	list_filters = ("medication_name", "medication_class", "default_dosage_form", "item_group", "disabled")
