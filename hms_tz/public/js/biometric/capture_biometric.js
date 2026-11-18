/**
 * Captures the patient's face or fingerprint for the given NHIF biometric method.
 * Any other method asks the user to confirm and returns an empty capture.
 * Resolves with { Data, fpCode }, or null when the user cancels.
 */
export async function captureBiometric(method, label) {
  if (method === "FACIAL") return new FacialRecognition({ label });
  if (method === "FINGERPRINT") return new Fingerprint({ label });
  const confirmed = await confirmWithoutBiometrics(method);
  return confirmed ? { Data: "", fpCode: "" } : null;
}

function confirmWithoutBiometrics(method) {
  return new Promise((resolve) => {
    frappe.confirm(
      `<div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
        <p class="text-center"><i>${__(
          "Biometric Method: {0} is only used when Patient is not able to take fingerprint or face.",
          [`<b>${frappe.utils.escape_html(method || "")}</b>`]
        )}</i></p>
      </div>
      <br>
      <p class="text-center"><i>${__(
        "Are you sure you want to continue?"
      )}</i></p>`,
      () => resolve(true),
      () => resolve(false)
    );
  });
}

window.captureBiometric = captureBiometric;
