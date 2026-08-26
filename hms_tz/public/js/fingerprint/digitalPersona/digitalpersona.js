import {
  FingerprintReader,
  SampleFormat,
  QualityCode,
} from "@digitalpersona/devices";

export class DigitalPersona {
  constructor() {
    this.dpReader = null;
    this.qualityReported = null;
    this.samples = null;
    this.fingerprintAcquired = false;
    this.initialized = false;

    // Event handlers will be set by the main fingerprint manager
    this.onDeviceConnected = null;
    this.onDeviceDisconnected = null;
    this.onSamplesAcquired = null;
    this.onQualityReported = null;
    this.onAcquisitionStarted = null;
    this.onCommunicationFailed = null;
    this.onReaderError = null;
  }

  initializeEventHandlers(callbacks) {
    this.onDeviceConnected = callbacks.onDeviceConnected;
    this.onDeviceDisconnected = callbacks.onDeviceDisconnected;
    this.onSamplesAcquired = callbacks.onSamplesAcquired;
    this.onQualityReported = callbacks.onQualityReported;
    this.onAcquisitionStarted = callbacks.onAcquisitionStarted;
    this.onCommunicationFailed = callbacks.onCommunicationFailed;
    this.onReaderError = callbacks.onReaderError;

    // Initialize the reader now that we have callbacks
    this.initializeReader();
  }

  handleDeviceConnected = (event) => {
    console.log("DigitalPersona Device Connected: ", event);
    if (this.onDeviceConnected) {
      this.onDeviceConnected(event);
    }
  };

  handleDeviceDisconnected = (event) => {
    console.log("DigitalPersona Device Disconnected: ", event);
    if (this.onDeviceDisconnected) {
      this.onDeviceDisconnected(event);
    }
  };

  handleSamplesAcquired = async (event) => {
    if (this.qualityReported !== QualityCode.Good) {
      frappe.msgprint(__("Fingerprint quality is poor. Please try again."));
      return;
    }

    try {
      this.samples = event.samples;
      this.fingerprintAcquired = true;

      if (this.onSamplesAcquired) {
        this.onSamplesAcquired(event.samples, "digitalpersona");
      }
    } catch (error) {
      console.error("DigitalPersona SampleAcquired Error:", error);
      frappe.msgprint(__("Fingerprint scan failed. Please try again."));
    }
  };

  handleReaderError = (event) => {
    console.error("DigitalPersona Reader Error:", event);
    if (this.onReaderError) {
      this.onReaderError(event);
    }
  };

  handleCommunicationFailed = (event) => {
    console.error("DigitalPersona Communication Error:", event);
    // Only pass communication failures to parent if we're actually scanning
    if (this.onCommunicationFailed) {
      this.onCommunicationFailed(event);
    }
  };

  handleAcquisitionStarted = (event) => {
    console.log("DigitalPersona Acquisition Started", event);
    if (this.onAcquisitionStarted) {
      this.onAcquisitionStarted(event);
    }
  };

  handleQualityReported = (event) => {
    console.log("DigitalPersona QualityReported started", event);
    this.qualityReported = event.quality;

    if (this.onQualityReported) {
      this.onQualityReported(event.quality);
    }

    if (event.quality !== QualityCode.Good) {
      console.log(
        `DigitalPersona fingerprint quality is poor: ${event.quality}`
      );
      this.resetDeviceState();
    }
  };

  async enumerateDevices() {
    try {
      // Initialize reader if not already done
      this.initializeReader();

      if (!this.dpReader) {
        throw new Error("DigitalPersona reader not available");
      }

      const dpDevices = await this.dpReader.enumerateDevices();
      return dpDevices.map((device, index) => ({
        name: `DIGITAL PERSONA U4500`,
        type: "digitalpersona",
        originalDevice: device,
      }));
    } catch (error) {
      console.warn("DigitalPersona devices not available:", error);
      return [];
    }
  }

  async startScan(device) {
    if (!this.dpReader) {
      throw new Error("DigitalPersona reader not initialized");
    }

    const deviceId = device.deviceId || device;
    // await this.dpReader.startAcquisition(SampleFormat.PngImage, deviceId);
    await this.dpReader.startAcquisition(SampleFormat.Compressed, deviceId); // to support WSQ format
  }

  async resetDeviceState() {
    try {
      if (this.dpReader) {
        await this.dpReader.stopAcquisition();
      }
    } catch (error) {
      console.error("Error resetting DigitalPersona device state:", error);
    }
  }

  formatFingerprintImage(sample) {
    // For DigitalPersona
    // let base64Data = sample.replace(/-/g, "+").replace(/_/g, "/");
    // return `data:image/bmp;base64,${sample}`;
    return "/assets/hms_tz/images/fingerprint.png";
  }

  destroy() {
    if (this.dpReader) {
      this.dpReader.off();
      this.resetDeviceState();
    }
  }

  initializeReader() {
    if (!this.initialized && typeof FingerprintReader !== "undefined") {
      try {
        this.dpReader = new FingerprintReader();
        this.initialized = true;

        // Initialize event handlers if callbacks are already set
        if (this.onCommunicationFailed) {
          this.dpReader.on(
            "CommunicationFailed",
            this.handleCommunicationFailed
          );
          this.dpReader.on("DeviceConnected", this.handleDeviceConnected);
          this.dpReader.on(
            "DeviceDisconnected",
            this.handleDeviceDisconnected
          );
          this.dpReader.on(
            "AcquisitionStarted",
            this.handleAcquisitionStarted
          );
          this.dpReader.on("QualityReported", this.handleQualityReported);
          this.dpReader.on("SamplesAcquired", this.handleSamplesAcquired);
          this.dpReader.on("ErrorOccurred", this.handleReaderError);
        }
      } catch (error) {
        console.error("Failed to initialize DigitalPersona reader:", error);
      }
    }
  }
}
