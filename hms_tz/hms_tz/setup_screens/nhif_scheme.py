from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class NHIFScheme(CompanyRecords):
	"""Setup screen of the NHIF schemes, which all companies share.

	The Get NHIF Schemes action of the Insurers screen downloads them; coverage plans name their scheme ID.
	A scheme is named by its scheme ID, so the ID is fixed once the scheme exists. Schemes are no setup step.
	"""

	doctype = "NHIF Scheme"
	company_field = None
	label = "NHIF scheme"
	plural_label = "NHIF schemes"
	extra_fields = {
		"scheme_id": {"reqd": 1, "set_only_once": 1},
		"scheme_name": {"reqd": 1},
	}
	match_field = "scheme_id"
	has_setup_step = False
