import frappe
from frappe import _

from hms_tz.hms_tz.doctype.setup_action_run.setup_action_run import get_action_runs
from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords

# HMS TZ Setting switch of each insurer connection.
CONNECTIONS = {"nhif": "enable_nhif_api", "jubilee": "enable_jubilee_api"}
CONNECTION_LABELS = {"nhif": "NHIF", "jubilee": "Jubilee"}


def get_action(key, label, method, doctype, connection, needs_caller=False):
	kwargs = {"caller": "Front End"} if needs_caller else {}
	return {
		"key": key,
		"label": label,
		"method": method,
		"doctype": doctype,
		"connection": connection,
		"kwargs": kwargs,
	}


NHIF = "hms_tz.nhif.nhif_api"
JUBILEE = "hms_tz.jubilee.api"
PRICES = f"{NHIF}.price_package"

# Insurers screen actions, with the labels of the Healthcare Insurance Company form buttons. Each runs, as a
# background job, the function the button runs or queues, and reports the record count of its DocType.
INSURANCE_ACTIONS = [
	get_action(*action)
	for action in (
		(
			"nhif_price_package",
			"Get NHIF Price Package",
			f"{PRICES}.get_price_package",
			"NHIF Price Package",
			"nhif",
		),
		(
			"nhif_process_records",
			"Only Process NHIF Records",
			f"{PRICES}.run_nhif_records",
			"Healthcare Service Insurance Coverage",
			"nhif",
		),
		(
			"nhif_copayment_items",
			"Get NHIF Co-Payment Items",
			f"{PRICES}.get_nhif_copayment_items",
			"NHIF Co-Payment Item",
			"nhif",
		),
		("nhif_schemes", "Get NHIF Schemes", f"{PRICES}.get_nhif_schemes", "NHIF Scheme", "nhif", True),
		(
			"nhif_service_types",
			"Get Service Types",
			f"{NHIF}.approval.get_approval_services",
			"NHIF Service Type",
			"nhif",
			True,
		),
		("nhif_item_types", "Get Item Types", f"{PRICES}.get_item_types", "NHIF Item Type", "nhif", True),
		("nhif_items", "Get NHIF Items", f"{PRICES}.get_nhif_items", "NHIF Item", "nhif"),
		(
			"nhif_visit_types",
			"Get Visit Types",
			f"{NHIF}.verification.get_visit_types",
			"Appointment Type",
			"nhif",
			True,
		),
		(
			"nhif_card_verifier",
			"Get Card Verifier",
			f"{NHIF}.verification.get_card_verifier",
			"Healthcare Card Verifier",
			"nhif",
			True,
		),
		(
			"nhif_admission_types",
			"Get Admission Types",
			f"{NHIF}.admission.get_admission_types",
			"Healthcare Admission Type",
			"nhif",
			True,
		),
		(
			"nhif_discharge_types",
			"Get Discharge Types",
			f"{NHIF}.admission.get_discharge_types",
			"Healthcare Discharge Type",
			"nhif",
			True,
		),
		(
			"nhif_ward_types",
			"Get Ward Types",
			f"{NHIF}.admission.get_ward_types",
			"Healthcare Ward Type",
			"nhif",
			True,
		),
		(
			"nhif_room_types",
			"Get Room Types",
			f"{NHIF}.admission.get_room_types",
			"Healthcare Room Type",
			"nhif",
			True,
		),
		(
			"nhif_points_of_care",
			"Get Points of Care",
			f"{NHIF}.reference.get_points_of_care",
			"Healthcare Points of Care",
			"nhif",
			True,
		),
		(
			"nhif_facilities",
			"Get Facilities",
			f"{NHIF}.facility.get_facilities",
			"Healthcare Facility",
			"nhif",
		),
		("nhif_diseases", "Get Diseases", f"{NHIF}.reference.get_diseases", "Code Value", "nhif"),
		("nhif_stg_records", "Get STG Records", f"{NHIF}.reference.get_stg_records", "NHIF STG", "nhif"),
		(
			"jubilee_packages",
			"Get Jubilee Packages",
			f"{JUBILEE}.price_package.get_price_package",
			"Jubilee Price Package",
			"jubilee",
		),
		(
			"jubilee_process_records",
			"Process Jubilee Records",
			f"{JUBILEE}.price_package.run_jubilee_records",
			"Healthcare Service Insurance Coverage",
			"jubilee",
		),
		(
			"jubilee_procedures",
			"Get Jubilee Procedures",
			f"{JUBILEE}.api.get_procedure_list",
			"Jubilee Procedure",
			"jubilee",
		),
	)
]


class InsuranceCompany(CompanyRecords):
	"""Setup screen of the company's insurers, where the manager confirms and changes them.

	The account fields take their company filters from the DocType JSON link_filters. The NHIF and Jubilee
	actions of the insurer form are offered as dropdowns for the connections switched on.
	"""

	doctype = "Healthcare Insurance Company"
	label = "insurance company"
	plural_label = "insurance companies"
	extra_fields = {
		"default_price_list": {
			"link_filters": [["Price List", "selling", "=", 1], ["Price List", "enabled", "=", 1]],
		},
		"no_of_days_for_follow_up": {},
		"hms_tz_has_price_discount": {},
		"hms_tz_price_discount": {},
		"disabled": {},
	}
	match_field = "insurance_company_name"

	@property
	def connections(self):
		"""Whether each connection is switched on in the company's HMS TZ Setting."""
		values = frappe.db.get_value(
			"HMS TZ Setting", {"company": self.company}, list(CONNECTIONS.values()), as_dict=True
		)
		return {connection: bool(values and values[field]) for connection, field in CONNECTIONS.items()}

	@property
	def actions(self):
		connections = self.connections
		return [action for action in INSURANCE_ACTIONS if connections[action["connection"]]]

	@property
	def action_groups(self):
		"""One dropdown per switched-on connection, for example "NHIF actions"."""
		actions = self.actions
		return [
			{
				"label": f"{label} actions",
				"actions": [
					{"key": action["key"], "label": action["label"]}
					for action in actions
					if action["connection"] == connection
				],
			}
			for connection, label in CONNECTION_LABELS.items()
			if any(action["connection"] == connection for action in actions)
		]

	@property
	def action_runs(self):
		return get_action_runs(self.company, [action["key"] for action in INSURANCE_ACTIONS])

	def get_action(self, key):
		"""One action of a switched-on connection."""
		action = next((action for action in self.actions if action["key"] == key), None)
		if not action:
			frappe.throw(
				_("{0} is not an insurance action of a connection that is on for {1}.").format(
					key, self.company
				)
			)
		return action
