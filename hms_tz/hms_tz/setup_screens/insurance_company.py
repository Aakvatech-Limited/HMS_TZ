import frappe
from frappe import _

from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords

# HMS TZ Setting switch of each insurer connection.
CONNECTIONS = {"nhif": "enable_nhif_api", "jubilee": "enable_jubilee_api"}
CONNECTION_LABELS = {"nhif": "NHIF", "jubilee": "Jubilee"}


def get_action(key, label, method, connection, needs_caller=False):
	kwargs = {"caller": "Front End"} if needs_caller else {}
	return {"key": key, "label": label, "method": method, "connection": connection, "kwargs": kwargs}


NHIF = "hms_tz.nhif.nhif_api"
JUBILEE = "hms_tz.jubilee.api"

# Insurers screen actions: the same methods and arguments as the Healthcare Insurance Company form buttons.
INSURANCE_ACTIONS = [
	get_action(
		"nhif_price_package",
		"Get NHIF Price Package",
		f"{NHIF}.price_package.enqueue_get_nhif_price_packages",
		"nhif",
	),
	get_action(
		"nhif_process_records",
		"Only Process NHIF Records",
		f"{NHIF}.price_package.process_nhif_records",
		"nhif",
	),
	get_action(
		"nhif_copayment_items",
		"Get NHIF Co-Payment Items",
		f"{NHIF}.price_package.enqueue_get_nhif_copayment_items",
		"nhif",
	),
	get_action("nhif_schemes", "Get NHIF Schemes", f"{NHIF}.price_package.get_nhif_schemes", "nhif", True),
	get_action(
		"nhif_service_types", "Get Service Types", f"{NHIF}.approval.get_approval_services", "nhif", True
	),
	get_action("nhif_item_types", "Get Item Types", f"{NHIF}.price_package.get_item_types", "nhif", True),
	get_action("nhif_items", "Get NHIF Items", f"{NHIF}.price_package.enqueue_fetch_nhif_items", "nhif"),
	get_action("nhif_visit_types", "Get Visit Types", f"{NHIF}.verification.get_visit_types", "nhif", True),
	get_action(
		"nhif_card_verifier", "Get Card Verifier", f"{NHIF}.verification.get_card_verifier", "nhif", True
	),
	get_action(
		"nhif_admission_types", "Get Admission Types", f"{NHIF}.admission.get_admission_types", "nhif", True
	),
	get_action(
		"nhif_discharge_types", "Get Discharge Types", f"{NHIF}.admission.get_discharge_types", "nhif", True
	),
	get_action("nhif_ward_types", "Get Ward Types", f"{NHIF}.admission.get_ward_types", "nhif", True),
	get_action("nhif_room_types", "Get Room Types", f"{NHIF}.admission.get_room_types", "nhif", True),
	get_action(
		"nhif_points_of_care", "Get Points of Care", f"{NHIF}.reference.get_points_of_care", "nhif", True
	),
	get_action("nhif_facilities", "Get Facilities", f"{NHIF}.facility.enqueue_get_facilities", "nhif"),
	get_action("nhif_diseases", "Get Diseases", f"{NHIF}.reference.enqueue_get_diseases", "nhif"),
	get_action("nhif_stg_records", "Get STG Records", f"{NHIF}.reference.enqueue_get_stg_records", "nhif"),
	get_action(
		"jubilee_packages",
		"Get Jubilee Packages",
		f"{JUBILEE}.price_package.enqueue_get_jubilee_price_packages",
		"jubilee",
	),
	get_action(
		"jubilee_process_records",
		"Process Jubilee Records",
		f"{JUBILEE}.price_package.process_jubilee_records",
		"jubilee",
	),
	get_action(
		"jubilee_procedures",
		"Get Jubilee Procedures",
		f"{JUBILEE}.api.enqueue_get_jubilee_procedures",
		"jubilee",
	),
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

	def run_action(self, key):
		"""Run one action of a switched-on connection, the way its insurer form button does."""
		action = next((action for action in self.actions if action["key"] == key), None)
		if not action:
			frappe.throw(
				_("{0} is not an insurance action of a connection that is on for {1}.").format(
					key, self.company
				)
			)
		return frappe.get_attr(action["method"])(company=self.company, **action["kwargs"])
