import { ref } from "vue";
import "@desk/fingerprint/digitalPersona/digitalpersona-shims.js";
import { DigitalPersona } from "@desk/fingerprint/digitalPersona/digitalpersona.js";
import { MFS100 } from "@desk/fingerprint/mantra/mfs100.js";
import { MFS500 } from "@desk/fingerprint/mantra/mfs500.js";
import { loadDigitalPersonaSDK } from "@desk/utils";

export const FINGER_CODES = [
  { label: "Right thumb", value: "R1" },
  { label: "Right index", value: "R2" },
  { label: "Right middle", value: "R3" },
  { label: "Right ring", value: "R4" },
  { label: "Right little", value: "R5" },
  { label: "Left thumb", value: "L1" },
  { label: "Left index", value: "L2" },
  { label: "Left middle", value: "L3" },
  { label: "Left ring", value: "L4" },
  { label: "Left little", value: "L5" },
];

const DIGITAL_PERSONA_SDK =
  "/assets/hms_tz/js/fingerprint/digitalPersona/modules/WebSdk/index.js";

/** The desk drivers report errors through frappe.msgprint; give them one on this page. */
const shimDeskGlobals = (onError) => {
  window.frappe = window.frappe || {};
  window.frappe.msgprint = window.frappe.msgprint || onError;
  window.__ = window.__ || ((text) => text);
};

/** Reader devices from the same drivers the desk uses, in the desk's priority order. */
export function useFingerprintScanner({ onError }) {
  const devices = ref([]);
  const scanning = ref(false);
  const drivers = {
    mfs500: new MFS500(),
    mfs100: new MFS100(),
    digitalpersona: new DigitalPersona(),
  };
  let onSample = null;

  const handlers = {
    onSamplesAcquired: (samples, deviceType) => {
      scanning.value = false;
      const sample = samples?.[0];
      const data = deviceType === "digitalpersona" ? sample?.Data : sample;
      const image = drivers[deviceType].formatFingerprintImage(sample);
      onSample?.({ data, image });
    },
    onCommunicationFailed: (event) => {
      scanning.value = false;
      onError(
        `Fingerprint reader communication failed: ${event?.message || ""}`
      );
    },
    onReaderError: (event) => {
      scanning.value = false;
      onError(`Fingerprint reader error: ${event?.message || ""}`);
    },
    onDeviceConnected: () => {},
    onDeviceDisconnected: () => {},
    onQualityReported: () => {},
    onAcquisitionStarted: () => {},
  };

  const enumerateDevices = async () => {
    shimDeskGlobals((message) => onError(String(message)));
    loadDigitalPersonaSDK(DIGITAL_PERSONA_SDK).catch(() => {});
    for (const driver of Object.values(drivers)) {
      driver.initializeEventHandlers(handlers);
    }
    for (const driver of [
      drivers.mfs500,
      drivers.mfs100,
      drivers.digitalpersona,
    ]) {
      try {
        devices.value = await driver.enumerateDevices();
      } catch {
        devices.value = [];
      }
      if (devices.value.length) return devices.value;
    }
    return devices.value;
  };

  const scan = async (device, callback) => {
    onSample = callback;
    scanning.value = true;
    try {
      if (device.type === "mfs500") await drivers.mfs500.startScan(device);
      else if (device.type === "mfs100") await drivers.mfs100.startScan();
      else await drivers.digitalpersona.startScan(device.originalDevice);
    } catch (error) {
      scanning.value = false;
      onError(error?.message || "Fingerprint scan failed");
    }
  };

  const destroy = async () => {
    onSample = null;
    scanning.value = false;
    await Promise.allSettled(
      Object.values(drivers).map((driver) => driver.destroy())
    );
  };

  return { devices, scanning, enumerateDevices, scan, destroy };
}
