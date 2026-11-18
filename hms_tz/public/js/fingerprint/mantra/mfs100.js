export class MFS100 {
  constructor() {
    this.samples = null;
    this.fingerprintAcquired = false;

    // Track active scan operations
    this.isScanning = false;
    this.currentScanController = null;

    // Event handlers will be set by the main fingerprint manager
    this.onSamplesAcquired = null;
  }

  initializeEventHandlers(callbacks) {
    this.onSamplesAcquired = callbacks.onSamplesAcquired;
  }

  async enumerateDevices() {
    try {
      // Create a timeout promise
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error("Request timeout")), 10000);
      });

      const fetchPromise = fetch("https://localhost:8003/mfs100/info", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const response = await Promise.race([fetchPromise, timeoutPromise]);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log("MFS100 device info:", data);

      if (data && data.ErrorCode == "0") {
        return [
          {
            name: `${data.DeviceInfo.Make} ${data.DeviceInfo.Model}`,
            type: "mfs100",
            originalDevice: {
              name: `${data.DeviceInfo.Make} ${data.DeviceInfo.Model}`,
              status: data.ErrorDescription,
            },
          },
        ];
      } else if (data && data.ErrorCode && data.ErrorCode != "0") {
        console.warn(
          "MFS100 device error:",
          data.ErrorDescription || `Error code: ${data.ErrorCode}`
        );
        return [];
      }

      return [];
    } catch (error) {
      console.error("Error checking MFS100 devices:", error);
      return [];
    }
  }

  async startScan() {
    this.isScanning = true;
    this.currentScanController = new AbortController();

    try {
      const response = await fetch("https://localhost:8003/mfs100/capture", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          Quality: 70,
          Timeout: 30000, // milliseconds
          InitOnLoad: 1, // Initialize device on load
          TemplateFormat: "ISO",
          ImageFormat: "WSQ",
        }),
        signal: this.currentScanController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.ErrorCode == "0" && data.WsqImage) {
        this.samples = [data.WsqImage];
        this.fingerprintAcquired = true;

        if (this.onSamplesAcquired) {
          this.onSamplesAcquired(this.samples, "mfs100");
        }
      } else {
        const errorMsg =
          data.ErrorDescription || `Error code: ${data.ErrorCode}`;
        throw new Error(errorMsg);
      }
    } catch (error) {
      // Don't show error if scan was intentionally cancelled
      if (error.name === "AbortError") {
        console.log("MFS100 scan cancelled");
        return;
      }

      console.error("MFS100 capture error:", error);

      let errorMessage;
      if (error.name === "TypeError" && error.message.includes("fetch")) {
        errorMessage = __(
          "MFS100 service is not running. Please ensure the Mantra RD Service is installed and running on port 8003."
        );
      } else if (error.message.includes("timeout")) {
        errorMessage = __("Fingerprint capture timeout. Please try again.");
      } else {
        errorMessage = __(`Failed to capture fingerprint: ${error.message}`);
      }

      throw new Error(errorMessage, { cause: error });
    } finally {
      this.isScanning = false;
      this.currentScanController = null;
    }
  }

  async cancelScan() {
    console.log("Cancelling MFS100 scan operation...");

    // Abort the current fetch request if active
    if (this.isScanning && this.currentScanController) {
      this.currentScanController.abort();
      console.log("MFS100 scan request aborted");
    }

    // Reset scan state immediately
    this.isScanning = false;
    this.currentScanController = null;

    // Note: MFS100 service doesn't provide an uninit endpoint
    // The device will automatically reset when the capture request is aborted
    console.log("MFS100 scan cancelled - device will reset automatically");
  }

  formatFingerprintImage(sample) {
    return sample.startsWith("data:")
      ? sample
      : `data:image/bmp;base64,${sample}`;
  }

  async resetDeviceState() {
    // For MFS100, no specific reset needed as it's stateless
    console.log("MFS100 device reset - no action needed (stateless)");
  }

  async destroy() {
    console.log("Destroying MFS100 fingerprint connection...");

    try {
      await this.cancelScan();

      console.log("MFS100 manager destroyed and device connection terminated");
    } catch (error) {
      console.warn("Error during MFS100 device cleanup:", error);
      // Don't throw the error as destroy should be non-blocking
    }

    // Reset internal state
    this.samples = null;
    this.fingerprintAcquired = false;
    this.onSamplesAcquired = null;
    this.isScanning = false;
    this.currentScanController = null;
  }
}
