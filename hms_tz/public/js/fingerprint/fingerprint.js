import { loadDigitalPersonaSDK } from "./../utils";
import { DigitalPersona } from "./digitalPersona/digitalpersona.js";
import { FINGERPRINT_DRIVER_DOWNLOADS } from "./drivers.js";
import { MFS100 } from "./mantra/mfs100.js";
import { MFS500 } from "./mantra/mfs500.js";

// Load DigitalPersona SDK
loadDigitalPersonaSDK(
  "/assets/hms_tz/js/fingerprint/digitalPersona/modules/WebSdk/index.js"
)
  .then(() => {
    console.log("DigitalPersona SDK loaded successfully.");
  })
  .catch((error) => {
    console.error("Failed to load DigitalPersona SDK:", error);
  });

export class Fingerprint {
  constructor(opts) {
    this.label = opts.label || "Send Request";

    this.mfs500 = new MFS500();
    this.mfs100 = new MFS100();
    this.digitalPersona = new DigitalPersona();

    // Device management
    this.allDevices = [];
    this.selectedDevice = null;
    this.selectedFinger = null;
    this.samples = null;
    this.fingerprintAcquired = false;
    this.currentDeviceType = null; // 'mfs500', 'mantra', or 'digitalpersona'
    this.deviceScanningComplete = false;
    this.onChangeTrigger = false; // Flag to prevent multiple onchange triggers

    return new Promise((resolve, reject) => {
      this.fingerprintPromiseResolve = resolve;
      this.fingerprintPromiseReject = reject;
      this.init();
    });
  }

  async init() {
    // Initialize event handlers for both devices
    this.initializeEventHandlers();

    this.showDialog();

    try {
      await this.enumerateAllDevices();
      this.deviceScanningComplete = true;

      this.updateDialog();
    } catch (err) {
      this.deviceScanningComplete = true;

      this.updateDialog();
      this.handleError(err, "init");
    }
  }

  initializeEventHandlers() {
    const callbacks = {
      onDeviceConnected: () => {
        console.log("Device Connected: ", this.selectedDevice);
      },
      onDeviceDisconnected: () => {
        // this.enumerateAllDevices().then(() => {
        //   this.deviceScanningComplete = true;
        //   this.updateDialog();
        // });
      },
      onSamplesAcquired: (samples, deviceType) => {
        this.samples = samples;
        this.currentDeviceType = deviceType;
        // this.showFingerprintImage(this.samples[0]);
        this.fingerprintAcquired = true;
        this.getFingerprintData();
      },
      onQualityReported: (quality) => {
        console.log("Quality Reported:", quality);
        // Quality handling is done in device-specific classes
      },
      onAcquisitionStarted: (event) => {
        console.log("Acquisition Started", event);
      },
      onCommunicationFailed: (event) => {
        console.error("Communication Error:", event);
        // if (this.fingerprintAcquired === false && this.currentDeviceType && this.selectedDevice && this.deviceScanningComplete) {
        //   frappe.show_alert({
        //     message: __("Failed to communicate with device, please try again..!"),
        //     indicator: "red",
        //   });
        // }
      },
      onReaderError: (event) => {
        console.error("Reader Error:", event);
      },
    };

    this.mfs500.initializeEventHandlers(callbacks);
    this.mfs100.initializeEventHandlers(callbacks);
    this.digitalPersona.initializeEventHandlers(callbacks);
  }

  async enumerateAllDevices() {
    this.allDevices = [];

    // Priority 1: MFS500 (Mantra MorFinAuth) - highest priority
    try {
      const mfs500Devices = await this.mfs500.enumerateDevices();
      console.log("MFS500 Devices:", mfs500Devices);
      this.allDevices.push(...mfs500Devices);
    } catch (error) {
      console.warn("MFS500 devices not available:", error.message);
    }

    // Priority 2: MFS100 (Mantra RD Service)
    if (!this.allDevices.length) {
      try {
        const mfs100Devices = await this.mfs100.enumerateDevices();
        this.allDevices.push(...mfs100Devices);
      } catch (error) {
        console.warn("MFS100 devices not available:", error.message);
      }
    }

    // Priority 3: DigitalPersona
    if (!this.allDevices.length) {
      try {
        const dpDevices = await this.digitalPersona.enumerateDevices();
        this.allDevices.push(...dpDevices);
      } catch (error) {
        console.warn("DigitalPersona devices not available:", error.message);
      }
    }
  }

  handleError = (error, stage) => {
    console.error(`Error at ${stage}:`, error);
    this.resetDeviceState();
  };

  resetDeviceState = async () => {
    try {
      if (this.currentDeviceType === "digitalpersona") {
        await this.digitalPersona.resetDeviceState();
      } else if (this.currentDeviceType === "mfs100") {
        await this.mfs100.resetDeviceState();
      } else if (this.currentDeviceType === "mfs500") {
        await this.mfs500.resetDeviceState();
      }
    } catch (error) {
      console.error("Error resetting device state:", error);
    }
  };

  destroy = async () => {
    this.dialog.hide();

    // Cleanup all device handlers
    try {
      await Promise.all([
        this.mfs500.destroy(),
        this.mfs100.destroy(),
        this.digitalPersona.destroy(),
      ]);
    } catch (error) {
      console.warn("Error during device cleanup:", error);
      // Continue with cleanup even if there are errors
    }

    // Reset internal state
    this.selectedDevice = null;
    this.selectedFinger = null;
    this.samples = null;
    this.fingerprintAcquired = false;
    this.currentDeviceType = null;
    this.deviceScanningComplete = false;
    this.onChangeTrigger = false;
  };

  showDialog = () => {
    this.dialog = new frappe.ui.Dialog({
      title: __("Scan Fingerprint"),
      // size: "small",
      width: 150,
      fields: [
        {
          fieldtype: "Select",
          label: __("Select Device"),
          fieldname: "device",
          options: [],
          reqd: 1,
          onchange: () => this.dialog.set_value("finger", ""),
        },
        {
          label: "Device connected Status",
          fieldtype: "HTML",
          fieldname: "device_connected_status",
          options: `<div id="device-connected-status">${__(
            "Scanning for devices..."
          )}</div>`,
        },
        {
          fieldtype: "Column Break",
          fieldname: "column_break_1",
        },
        {
          fieldtype: "Select",
          label: __("Select Finger to Scan"),
          fieldname: "finger",
          options: [
            { label: __("Right Thumb (R1)"), value: "R1" },
            { label: __("Right Index (R2)"), value: "R2" },
            { label: __("Right Middle (R3)"), value: "R3" },
            { label: __("Right Ring (R4)"), value: "R4" },
            { label: __("Right Little (R5)"), value: "R5" },
            { label: __("Left Thumb (L1)"), value: "L1" },
            { label: __("Left Index (L2)"), value: "L2" },
            { label: __("Left Middle (L3)"), value: "L3" },
            { label: __("Left Ring (L4)"), value: "L4" },
            { label: __("Left Little (L5)"), value: "L5" },
          ],
          reqd: 1,
          onchange: () => {
            // Prevent multiple simultaneous executions
            if (this.onChangeTrigger) {
              return;
            }

            const fingerValue = this.dialog.get_value("finger");
            if (fingerValue) {
              this.onChangeTrigger = true;

              // Use setTimeout to ensure the flag is reset even if there's an error
              setTimeout(async () => {
                this.toggleFingerprintField().finally(() => {
                  this.onChangeTrigger = false;
                });
              }, 10);
            }
          },
        },
        {
          fieldtype: "Section Break",
          fieldname: "section_break_1",
        },
        {
          label: "Device Disconnected Status",
          fieldtype: "HTML",
          fieldname: "device_disconnected_status",
          options: `<div id="device-disconnected-status"></div>`,
        },
        {
          fieldtype: "HTML",
          fieldname: "fingerprint",
          options: `<div id="fingerprint-image"></div>`,
        },
      ],
      secondary_action_label: __("Cancel"),
      secondary_action: async () => {
        try {
          await this.destroy();
        } catch (error) {
          console.error("Error during cancel operation:", error);
          // Still proceed with cancellation even if cleanup fails
        }
      },
    });

    // this.dialog.$wrapper.find('.modal-content').css('width', '550px');
    this.dialog.show();
  };

  updateDialog = () => {
    const hasDevices = this.allDevices.length > 0;
    if (hasDevices) {
      const deviceOptions = this.allDevices.map((device) => ({
        label: device.name,
        value: device.name,
      }));

      this.dialog.set_df_property("device", "options", deviceOptions);

      if (!this.selectedDevice) {
        this.selectedDevice = this.allDevices[0].name;
        this.dialog.set_value("device", this.selectedDevice);
      }

      this.dialog.set_df_property("device", "hidden", 0);
      this.dialog.set_df_property("finger", "hidden", 0);
      this.dialog.set_df_property("fingerprint", "hidden", 0);
    } else {
      this.dialog.set_df_property("device", "hidden", 1);
      this.dialog.set_df_property("finger", "hidden", 1);
      this.dialog.set_df_property("fingerprint", "hidden", 1);
    }

    // Update device status fields based on current state
    if (!this.deviceScanningComplete) {
      this.updateDeviceConnectedStatus(
        `<div style="color: orange; padding: 5px;">${__(
          "Scanning for devices..."
        )}</div>`
      );
      this.updateDeviceDisconnectedStatus("");
    } else if (hasDevices) {
      this.updateDeviceConnectedStatus(
        `<div style="color: green; padding: 2px;">${__(
          "Device Connected"
        )}</div>`
      );
      this.updateDeviceDisconnectedStatus("");
    } else {
      this.updateDeviceConnectedStatus("");
      this
        .updateDeviceDisconnectedStatus(`<div style="padding: 5px; line-height: 1.6;">
                <strong>No Device Connected.</strong><br>
                Please download and install drivers:
              </div>
              <div style="padding: 0 10px;">
                <ul style="margin: 10px 0; padding-left: 40px;">
                  ${FINGERPRINT_DRIVER_DOWNLOADS.map(
                    ({ label, url }) => `<li style="margin: 5px 0;">
                    <a href="${url}" target="_blank"
                    style='color: blue; font-weight: bold;'>${label}</a>
                  </li>`
                  ).join("")}
                </ul>
              </div>
              <div style="padding: 0 15px 15px; font-size: 12px; color: #666;">
                After installation, restart your browser and ensure services are running.<br>
              </div>`);
    }
  };

  toggleFingerprintField = async () => {
    if (this.dialog.get_value("finger")) {
      const fingerprintDiv = this.dialog.get_field("fingerprint").$wrapper;
      fingerprintDiv.html(
        `<div id="fingerprint-image" style="width: 100px; height: 100px; border: 1px solid black;
                    display: flex; justify-content: center; align-items: center; text-align: center; margin-left: 200px;">
                    <span>Place a finger on the device</span>
                </div>`
      );

      await this.startScan();
    }
  };

  getFingerprintData = async () => {
    if (!this.fingerprintAcquired || !this.samples) {
      frappe.msgprint(__("Please scan your fingerprint first."));
      return;
    }

    if (!this.selectedFinger) {
      frappe.msgprint(__("Please select a finger position."));
      return;
    }

    if (this.fingerprintPromiseResolve) {
      let fData;
      if (this.currentDeviceType === "digitalpersona") {
        console.log("this.samples:", this.samples);
        fData = this.samples[0].Data;
      } else {
        fData = this.samples[0];
      }
      console.log("fData: ", fData);

      const data = {
        Data: fData,
        fpCode: this.selectedFinger,
      };

      this.fingerprintPromiseResolve(data);
    }

    await this.destroy();
  };

  updateDeviceConnectedStatus = (content) => {
    const dcs_wrapper =
      this.dialog.fields_dict.device_connected_status.$wrapper;
    dcs_wrapper.find("#device-connected-status").html(content);
  };

  updateDeviceDisconnectedStatus = (content) => {
    const dds_wrapper =
      this.dialog.fields_dict.device_disconnected_status.$wrapper;
    dds_wrapper.find("#device-disconnected-status").html(content);
  };

  showFingerprintImage = (sample) => {
    const d = this.dialog.get_field("fingerprint").$wrapper;

    if (sample) {
      let imageSrc;

      if (this.currentDeviceType === "mfs500") {
        imageSrc = this.mfs500.formatFingerprintImage(sample);
      } else if (this.currentDeviceType === "mfs100") {
        imageSrc = this.mfs100.formatFingerprintImage(sample);
      } else {
        imageSrc = this.digitalPersona.formatFingerprintImage(sample);
      }

      d.html(`
          <div id="fingerprint-image"
              style="width: 100px; height: 140px; border: 1px solid black;
                  display: flex; flex-direction: column; align-items: center; margin-left: 200px;
                  justify-content: center; text-align: center;">
              <img src="${imageSrc}" alt="Fingerprint" style="width: 100px; height: 140px; background-color: white;">
          </div>
      `);
    }
  };

  startScan = async () => {
    this.selectedFinger = this.dialog.get_value("finger");
    if (!this.selectedFinger) {
      frappe.msgprint(__("Please select a finger to scan."));
      return;
    }

    const device = this.dialog.get_value("device");
    if (!device) {
      frappe.msgprint(__("Please select a device."));
      return;
    }

    // Find the selected device
    const selectedDeviceInfo = this.allDevices.find((d) => d.name === device);
    if (!selectedDeviceInfo) {
      frappe.msgprint(__("Selected device not found."));
      return;
    }

    this.selectedDevice = device;
    this.currentDeviceType = selectedDeviceInfo.type;

    try {
      if (selectedDeviceInfo.type === "mfs500") {
        await this.mfs500.startScan(selectedDeviceInfo);
      } else if (selectedDeviceInfo.type === "digitalpersona") {
        await this.digitalPersona.startScan(selectedDeviceInfo.originalDevice);
      } else if (selectedDeviceInfo.type === "mfs100") {
        await this.mfs100.startScan();
      }
    } catch (error) {
      this.handleError(error, "startScan");
    }
  };
}

// Make Fingerprint available globally
window.Fingerprint = Fingerprint;
