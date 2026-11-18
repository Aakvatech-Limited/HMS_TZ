/**
 * Mantra MFS500 Fingerprint Device Integration
 *
 * This module integrates with the MorFinAuthClientService running on the local machine.
 * The service must be installed and running on the Windows client machine.
 *
 * Driver: MorFin_Driver_1.4.0.0.exe
 * Client Service: MorFinAuthClientService.exe
 *
 * Default port: 8030
 * Base URL: http://localhost:8030/morfinauth/
 */

export class MFS500 {
  constructor() {
    this.samples = null;
    this.fingerprintAcquired = false;

    this.isScanning = false;
    this.currentScanController = null;

    this.onSamplesAcquired = null;

    this.baseUrl = "http://localhost:8030/morfinauth/";
    this.connectedDevice = null;

    this.captureSettings = {
      Quality: 60,
      Timeout: 10,
    };
  }

  initializeEventHandlers(callbacks) {
    this.onSamplesAcquired = callbacks.onSamplesAcquired;
  }

  /**
   * Make a POST request to the MorFinAuth service
   */
  async postToService(method, jsonData = null) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      const options = {
        method: "POST",
        headers: {
          "Content-Type": "application/json; charset=utf-8",
        },
        signal: controller.signal,
      };

      if (jsonData) {
        options.body = JSON.stringify(jsonData);
      }

      const response = await fetch(`${this.baseUrl}${method}`, options);
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { httpStatus: true, data: data };
    } catch (error) {
      console.error(`MFS500 API error (${method}):`, error);
      return { httpStatus: false, err: this.getHttpError(error) };
    }
  }

  /**
   * Get HTTP error message
   */
  getHttpError(error) {
    if (error.name === "AbortError") {
      return "Request timeout";
    } else if (error.message.includes("fetch")) {
      return "Service Unavailable";
    } else if (error.message.includes("404")) {
      return "Requested page not found";
    } else if (error.message.includes("500")) {
      return "Internal Server Error";
    }
    return error.message || "Unhandled Error";
  }

  /**
   * Get device info from MorFinAuth service
   */
  async getDeviceInfo(connectedDvc = "", clientKey = "") {
    const request = {
      ConnectedDvc: connectedDvc,
      ClientKey: clientKey,
    };
    return await this.postToService("info", request);
  }

  /**
   * Check if device is connected
   */
  async isDeviceConnected(connectedDvc = "") {
    const request = {
      ConnectedDvc: connectedDvc,
    };
    return await this.postToService("checkdevice", request);
  }

  /**
   * Initialize device
   */
  async initDevice(connectedDvc = "", clientKey = "") {
    const request = {
      ConnectedDvc: connectedDvc,
      ClientKey: clientKey,
    };
    return await this.postToService("initdevice", request);
  }

  /**
   * Uninitialize device
   */
  async uninitDevice() {
    return await this.postToService("uninitdevice");
  }

  /**
   * Get list of supported devices
   */
  async getSupportedDeviceList() {
    return await this.postToService("supporteddevicelist");
  }

  /**
   * Get list of connected devices
   */
  async getConnectedDeviceList() {
    return await this.postToService("connecteddevicelist");
  }

  /**
   * Capture fingerprint
   */
  async captureFinger(quality, timeout) {
    const request = {
      Quality: quality,
      TimeOut: timeout,
    };
    return await this.postToService("capture", request);
  }

  /**
   * Get fingerprint image
   * @param imgFormat - 0: WSQ, 1: BMP, 2: JPEG
   */
  async getImage(imgFormat = 0) {
    const request = {
      ImgFormat: imgFormat,
    };
    return await this.postToService("getimage", request);
  }

  /**
   * Get fingerprint template
   * @param tmpFormat - 0: ISO, 1: ANSI
   */
  async getTemplate(tmpFormat = 0) {
    const request = {
      TmpFormat: tmpFormat,
    };
    return await this.postToService("gettemplate", request);
  }

  /**
   * Verify fingerprint against template
   */
  async verifyFinger(probFMR, galleryFMR, tmpFormat = 0) {
    const request = {
      ProbTemplate: probFMR,
      GalleryTemplate: galleryFMR,
      TmpFormat: tmpFormat,
    };
    return await this.postToService("verify", request);
  }

  /**
   * Match fingerprint (capture and verify in one step)
   */
  async matchFinger(quality, timeout, galleryFMR, tmpFormat = 0) {
    const request = {
      Quality: quality,
      TimeOut: timeout,
      GalleryTemplate: galleryFMR,
      TmpFormat: tmpFormat,
    };
    return await this.postToService("match", request);
  }

  /**
   * Extract device name from ErrorDescription
   * e.g., "Connected Device :MFS500" -> "MFS500"
   */
  extractDeviceNameFromDescription(errorDescription) {
    if (!errorDescription) return null;

    // Handle format: "Connected Device :MFS500" or "Connected Device:MFS500"
    if (errorDescription.includes(":")) {
      const parts = errorDescription.split(":");
      if (parts.length >= 2) {
        return parts[1].trim();
      }
    }

    return null;
  }

  /**
   * Enumerate connected MFS500 devices
   */
  async enumerateDevices() {
    try {
      const result = await this.getConnectedDeviceList();

      if (!result.httpStatus) {
        console.log(
          "MFS500: MorFinAuthClientService not available -",
          result.err
        );
        return [];
      }

      const data = result.data;
      if (data && (data.ErrorCode === "0" || data.ErrorCode === 0)) {
        const devices = [];
        let deviceName = null;

        deviceName = this.extractDeviceNameFromDescription(
          data.ErrorDescription
        );

        if (deviceName) {
          const device = {
            name: `MANTRA ${deviceName}`,
            type: "mfs500",
            deviceId: deviceName,
            originalDevice: {
              name: deviceName,
              status: "Connected",
            },
          };

          devices.push(device);
          this.connectedDevice = device;

          // await this.initDevice(deviceName);
          return devices;
        }
      }

      console.log("MFS500: No devices found");
      return [];
    } catch (error) {
      console.error("Error checking MFS500 devices:", error);
      return [];
    }
  }

  /**
   * Start fingerprint capture
   */
  async startScan(deviceInfo = null) {
    this.isScanning = true;
    this.currentScanController = new AbortController();

    try {
      const deviceName =
        deviceInfo?.deviceId || this.connectedDevice?.deviceId || "";

      const initResult = await this.initDevice(deviceName);

      const captureResult = await this.captureFinger(
        this.captureSettings.Quality,
        this.captureSettings.Timeout
      );

      if (!captureResult.httpStatus) {
        throw new Error(captureResult.err || "Capture failed");
      }

      const data = captureResult.data;

      if (data && (data.ErrorCode === "0" || data.ErrorCode === 0)) {
        let wsqImage = null;

        const imageResult = await this.getImage(2); // 0 = WSQ format

        if (imageResult.httpStatus && imageResult.data) {
          wsqImage = imageResult.data.ImgData;
        }

        if (wsqImage) {
          this.samples = [wsqImage];
          this.fingerprintAcquired = true;

          if (this.onSamplesAcquired) {
            this.onSamplesAcquired(this.samples, "mfs500");
          }

          return wsqImage;
        } else {
          throw new Error("No WSQ fingerprint data in response");
        }
      } else {
        // Handle error
        const errorMsg = this.getErrorMessage(
          data?.ErrorCode,
          data?.ErrorDescription
        );
        throw new Error(errorMsg);
      }
    } catch (error) {
      // Don't show error if scan was intentionally cancelled
      if (error.name === "AbortError") {
        console.log("MFS500 scan cancelled");
        return;
      }

      console.error("MFS500 capture error:", error);

      let errorMessage;
      if (
        error.message === "Service Unavailable" ||
        error.message.includes("fetch")
      ) {
        errorMessage = __(
          "MFS500 service is not running. Please ensure MorFinAuthClientService is installed and running on port 8030."
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

  /**
   * Get human-readable error message from error code
   */
  getErrorMessage(errorCode, defaultMessage) {
    const errorMessages = {
      "-1": "Unknown error occurred",
      "-2": "Device not connected",
      "-3": "Device not initialized",
      "-4": "Capture failed",
      "-5": "Invalid parameter",
      "-6": "Capture timeout - no finger detected",
      "-7": "Poor quality fingerprint",
      "-8": "Device is busy",
      "-9": "Device communication error",
      "-10": "License error",
      "-1301": "Device not found",
      "-1302": "Device initialization failed",
      "-1303": "Capture already in progress",
      "-1304": "Invalid image quality",
      "-1305": "Invalid template format",
      "-1306": "Device disconnected during capture",
      "-1307": "Operation cancelled by user",
      "-1308": "Service not responding",
    };

    const code = String(errorCode);
    return errorMessages[code] || defaultMessage || `Error code: ${errorCode}`;
  }

  /**
   * Cancel ongoing scan operation
   */
  async cancelScan() {
    console.log("Cancelling MFS500 scan operation...");

    // Abort the current fetch request if active
    if (this.isScanning && this.currentScanController) {
      this.currentScanController.abort();
      console.log("MFS500 scan request aborted");
    }

    // Reset scan state immediately
    this.isScanning = false;
    this.currentScanController = null;

    // Uninitialize device
    try {
      await this.uninitDevice();
      console.log("MFS500 device uninitialized");
    } catch (error) {
      console.log("MFS500 uninit completed (may not be needed)");
    }

    console.log("MFS500 scan cancelled");
  }

  /**
   * Format fingerprint image for display
   */
  formatFingerprintImage(sample) {
    if (!sample) {
      return "/assets/hms_tz/images/fingerprint.png";
    }

    // Check if already has data URI prefix
    if (sample.startsWith("data:")) {
      return sample;
    }

    // For templates (ISO/ANSI), we can't display them as images
    // Return a placeholder fingerprint image
    return "/assets/hms_tz/images/fingerprint.png";
  }

  /**
   * Reset device state
   */
  async resetDeviceState() {
    console.log("MFS500 device reset");

    // Cancel any ongoing operations
    await this.cancelScan();

    // Reset internal state
    this.samples = null;
    this.fingerprintAcquired = false;
  }

  /**
   * Destroy and cleanup
   */
  async destroy() {
    console.log("Destroying MFS500 fingerprint connection...");

    try {
      await this.uninitDevice();
      console.log("MFS500 manager destroyed");
    } catch (error) {
      console.warn("Error during MFS500 device cleanup:", error);
    }

    // Reset internal state
    this.samples = null;
    this.fingerprintAcquired = false;
    this.onSamplesAcquired = null;
    this.isScanning = false;
    this.currentScanController = null;
    this.connectedDevice = null;
  }

  /**
   * Check if device service is available
   */
  async isServiceAvailable() {
    const result = await this.getConnectedDeviceList();
    return result.httpStatus;
  }

  /**
   * Get current capture settings
   */
  getCaptureSettings() {
    return { ...this.captureSettings };
  }

  /**
   * Update capture settings
   */
  setCaptureSettings(settings) {
    this.captureSettings = {
      ...this.captureSettings,
      ...settings,
    };
  }
}
