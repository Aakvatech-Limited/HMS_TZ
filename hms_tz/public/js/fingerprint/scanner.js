import "./digitalPersona/digitalpersona-shims.js";
import { loadDigitalPersonaSDK } from "../utils.js";
import { DigitalPersona } from "./digitalPersona/digitalpersona.js";
import { MFS100 } from "./mantra/mfs100.js";
import { MFS500 } from "./mantra/mfs500.js";

export const FINGER_CODES = [
  { label: "Right Thumb (R1)", value: "R1" },
  { label: "Right Index (R2)", value: "R2" },
  { label: "Right Middle (R3)", value: "R3" },
  { label: "Right Ring (R4)", value: "R4" },
  { label: "Right Little (R5)", value: "R5" },
  { label: "Left Thumb (L1)", value: "L1" },
  { label: "Left Index (L2)", value: "L2" },
  { label: "Left Middle (L3)", value: "L3" },
  { label: "Left Ring (L4)", value: "L4" },
  { label: "Left Little (L5)", value: "L5" },
];

const DIGITAL_PERSONA_SDK =
  "/assets/hms_tz/js/fingerprint/digitalPersona/modules/WebSdk/index.js";

let digitalPersonaSdk = null;

/**
 * Finds fingerprint readers and scans one finger, for desk and Vue dialogs.
 * Use one instance per dialog: destroy() detaches the reader events for good.
 */
export class FingerprintScanner {
  constructor({ onSample, onError }) {
    this.onSample = onSample;
    this.onError = onError;
    this.drivers = {
      mfs500: new MFS500(),
      mfs100: new MFS100(),
      digitalpersona: new DigitalPersona(),
    };
    this.activeDevice = null;
    this.finger = null;
    this.isScanning = false;
  }

  /** Readers of the first driver that finds any, in priority order: MFS500, MFS100, DigitalPersona. */
  async findDevices() {
    await this.loadDigitalPersonaSdk();
    this.attachDriverEvents();
    for (const driver of Object.values(this.drivers)) {
      const devices = await driver.enumerateDevices().catch(() => []);
      if (devices.length) return devices;
    }
    return [];
  }

  /** A finger change during a scan only changes the code sent with the sample. */
  async scan(device, finger) {
    this.finger = finger;
    if (this.isScanning) return;
    this.activeDevice = device;
    this.isScanning = true;
    try {
      const driver = this.drivers[device.type];
      if (device.type === "digitalpersona") {
        await driver.startScan(device.originalDevice);
      } else {
        await driver.startScan(device);
      }
    } catch (error) {
      this.reportError(error?.message || __("Fingerprint scan failed."));
    }
  }

  async destroy() {
    this.onSample = null;
    this.onError = null;
    await Promise.allSettled(
      Object.values(this.drivers).map((driver) => driver.destroy())
    );
  }

  loadDigitalPersonaSdk() {
    // The DigitalPersona reader needs the WebSdk global; a missing SDK only hides that reader
    digitalPersonaSdk ||= loadDigitalPersonaSDK(DIGITAL_PERSONA_SDK).catch(
      (error) => console.warn("DigitalPersona SDK not loaded:", error)
    );
    return digitalPersonaSdk;
  }

  attachDriverEvents() {
    const handlers = {
      onSamplesAcquired: (samples, deviceType) =>
        this.handleSample(samples?.[0], deviceType),
      onError: (message) => this.reportError(message),
      onCommunicationFailed: (event) =>
        this.reportDigitalPersonaError(
          __("Reader communication failed"),
          event
        ),
      onReaderError: (event) =>
        this.reportDigitalPersonaError(__("Reader error"), event),
      onDeviceConnected: () => {},
      onDeviceDisconnected: () => {},
      onQualityReported: () => {},
      onAcquisitionStarted: () => {},
    };
    for (const driver of Object.values(this.drivers)) {
      driver.initializeEventHandlers(handlers);
    }
  }

  handleSample(sample, deviceType) {
    this.isScanning = false;
    const data = deviceType === "digitalpersona" ? sample?.Data : sample;
    this.onSample?.({
      result: { Data: data, fpCode: this.finger },
      image: this.drivers[deviceType].formatFingerprintImage(sample),
    });
  }

  // The WebSdk reports these while it looks for its service, so only a DigitalPersona scan shows them
  reportDigitalPersonaError(prefix, event) {
    if (this.activeDevice?.type !== "digitalpersona") return;
    this.reportError(`${prefix}: ${event?.message || event?.error || ""}`);
  }

  reportError(message) {
    this.isScanning = false;
    console.error("Fingerprint:", message);
    this.onError?.(message);
  }
}
