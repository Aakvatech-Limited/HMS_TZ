from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class AppointmentType(CompanyRecords):
	"""Setup screen of the visit types (Appointment Types), which all companies share.

	NHIF visit types come from the Get Visit Types action of the Insurers screen. A visit type added here
	carries the NHIF visit type ID that NHIF authorization sends for it. It is named by its visit type
	name, so the name is fixed once it exists.
	"""

	doctype = "Appointment Type"
	company_field = None
	label = "visit type"
	plural_label = "visit types"
	extra_fields = {
		"appointment_type": {"set_only_once": 1},
		"source": {"fieldtype": "Select", "options": "Direct\nReferral\nExternal Referral"},
		"default_duration": {},
		"has_no_consultation_charges_for_cash": {},
		"has_no_consultation_charges_for_insurance": {},
		"disabled": {},
	}
	match_field = "appointment_type"
