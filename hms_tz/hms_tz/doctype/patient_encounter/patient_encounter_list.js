/*
(c) ESS 2015-16
*/
frappe.listview_settings["Patient Encounter"] = {
  filters: [
    ["docstatus", "!=", "2"],
    ["duplicated", "==", "0"],
  ],

  onload: function (listview) {
    listview.page.fields_dict["admission_service_unit_type"].get_query =
      function () {
        return {
          filters: {
            inpatient_occupancy: 1,
          },
        };
      };
    nhif_btns(listview);
  },
};

var nhif_btns = (listview) => {
  if (!frappe.user.has_role("Healthcare Practitioner")) {
    return;
  }

  frappe.call({
    method:
      "hms_tz.nhif.nhif_api.healthcare_practitioner.get_nhif_practitioner_login_status",
    args: {},
    callback: (r) => {
      let data = r.message;

      if (data.show_login) {
        login_to_nhif(listview);
      }

      if (data.show_logout) {
        logout_from_nhif(listview);
      }
    },
  });
};

var login_to_nhif = (listview) => {
  listview.page
    .add_inner_button(__("Login To NHIF"), async () => {
      let dialog = new frappe.ui.Dialog({
        title: __("<h4>Login To NHIF</h4>"),
        // width: 150,
        fields: [
          {
            fieldtype: "Select",
            label: "Biometric Method",
            fieldname: "biometric_method",
            options: [
              { value: "FINGERPRINT", label: __("FINGERPRINT") },
              { value: "FACIAL", label: __("FACIAL") },
              // { value: "NONE", label: __("NONE") },
            ],
            default: "FINGERPRINT",
            reqd: 1,
          },
        ],
        size: "small",
        primary_action_label: __("Next"),
        primary_action: async () => {
          let biometricData;
          let values = dialog.get_values();
          dialog.hide();

          if (values.biometric_method === "FACIAL") {
            biometricData = await new FacialRecognition({
              label: "Login To NHIF",
            });
            if (!biometricData) {
              frappe.msgprint(__("Face capture failed. Please try again."));
              return;
            }
          } else if (values.biometric_method === "FINGERPRINT") {
            biometricData = await new Fingerprint({ label: "Login To NHIF" });
            if (!biometricData) {
              frappe.msgprint(
                __("Fingerprint capture failed. Please try again.")
              );
              return;
            }
          } else {
            const confirmed = await new Promise((resolve) => {
              frappe.confirm(
                __(`
                  <div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
                  <p class="text-center"><i>Biometric Method: <b>${values.biometric_method}</b> is only used when Patient is not able to take fingerprint or face.</i></p>
                  </div>
                  <br>
                  <p class="text-center"><i>Are you sure you want to continue?</i></p>`),
                () => resolve(true),
                () => resolve(false)
              );
            });

            if (!confirmed) {
              return;
            }

            biometricData = { Data: "", fpCode: "" };
          }

          frappe.call({
            method: "hms_tz.nhif.nhif_api.attendance.login_practitioner",
            args: {
              fingerprint: biometricData.Data,
              fpcode: biometricData.fpCode,
            },
            async: true,
            freeze: true,
            freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
            callback: function (data) {
              if (data.message && data.message !== "Error") {
                frappe.utils.play_sound("submit");
              } else {
                frappe.utils.play_sound("error");
              }
            },
            onerror: function (data) {
              frappe.utils.play_sound("error");
            },
          });
        },
      });
      dialog.show();
    })
    .removeClass("btn-default")
    .addClass("btn-primary btn-sm");
};

var logout_from_nhif = (listview) => {
  listview.page
    .add_inner_button(__("Logout From NHIF"), async () => {
      frappe.call({
        method: "hms_tz.nhif.nhif_api.attendance.logout_practitioner",
        args: {},
        async: true,
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        callback: function (data) {
          if (data.message && data.message !== "Error") {
            frappe.utils.play_sound("submit");
          } else {
            frappe.utils.play_sound("error");
          }
        },
        onerror: function (data) {
          frappe.utils.play_sound("error");
        },
      });
    })
    .removeClass("btn-default")
    .addClass("btn-primary btn-sm");
};
