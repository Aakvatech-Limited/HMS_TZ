frappe.ui.form.on("Healthcare Insurance Company", {
  onload: function (frm) {
    add_nhif_actions_btn(frm);
    add_jubilee_actions_btn(frm);
  },
  refresh: function (frm) {
    add_nhif_actions_btn(frm);
    add_jubilee_actions_btn(frm);
  },
});

var add_nhif_actions_btn = function (frm) {
  if (!frm.doc.insurance_company_name.includes("NHIF")) {
    return;
  }

  frm.add_custom_button(
    __("Get NHIF Price Package"),
    function () {
      frappe.call({
        method:
          "hms_tz.nhif.nhif_api.price_package.enqueue_get_nhif_price_packages",
        args: { company: frm.doc.company },
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Only Process NHIF Records"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.price_package.process_nhif_records",
        args: { company: frm.doc.company },
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get NHIF Co-Payment Items"),
    function () {
      frappe.call({
        method:
          "hms_tz.nhif.nhif_api.price_package.enqueue_get_nhif_copayment_items",
        args: { company: frm.doc.company },
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get NHIF Schemes"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.price_package.get_nhif_schemes",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  // frm.add_custom_button(__('Get NHIF Products'), function () {
  //     frappe.call({
  //         method: 'hms_tz.nhif.nhif_api.price_package.get_nhif_products',
  //         args: {
  //             company: frm.doc.company,
  //             caller: 'Front End'
  //         },
  //         freeze: true,
  //         freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
  //         callback: function (data) {
  //             if (data.message) {
  //                 console.log(data.message)
  //             }
  //         }
  //     });
  // }, __('NHIF Actions'));

  frm.add_custom_button(
    __("Get Service Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.approval.get_approval_services",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Item Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.price_package.get_item_types",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get NHIF Items"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.price_package.enqueue_fetch_nhif_items",
        args: { company: frm.doc.company },
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Visit Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.verification.get_visit_types",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Card Verifier"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.verification.get_card_verifier",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Admission Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.admission.get_admission_types",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Discharge Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.admission.get_discharge_types",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Ward Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.admission.get_ward_types",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Room Types"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.admission.get_room_types",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Points of Care"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.reference.get_points_of_care",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Facilities"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.facility.enqueue_get_facilities",
        args: { company: frm.doc.company },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get Diseases"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.reference.enqueue_get_diseases",
        args: { company: frm.doc.company },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message) {
            console.log(data.message);
          }
        },
      });
    },
    __("NHIF Actions")
  );

  frm.add_custom_button(
    __("Get STG Records"),
    function () {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.reference.enqueue_get_stg_records",
        args: { company: frm.doc.company },
      });
    },
    __("NHIF Actions")
  );
};

var add_jubilee_actions_btn = (frm) => {
  if (!frm.doc.insurance_company_name.includes("Jubilee")) {
    return;
  }

  frm.add_custom_button(
    __("Get Jubilee Packages"),
    () => {
      frappe.call({
        method:
          "hms_tz.jubilee.api.price_package.enqueue_get_jubilee_price_packages",
        args: { company: frm.doc.company },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: (data) => {},
      });
    },
    __("Jubilee Actions")
  );

  frm.add_custom_button(
    __("Process Jubilee Records"),
    () => {
      frappe.call({
        method: "hms_tz.jubilee.api.price_package.process_jubilee_records",
        args: { company: frm.doc.company },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: (data) => {},
      });
    },
    __("Jubilee Actions")
  );

  frm.add_custom_button(
    __("Get Jubilee Procedures"),
    () => {
      frappe.call({
        method: "hms_tz.jubilee.api.api.enqueue_get_jubilee_procedures",
        args: {
          company: frm.doc.company,
          caller: "Front End",
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: (data) => {},
      });
    },
    __("Jubilee Actions")
  );
};
