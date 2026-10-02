import { callPiService } from "./piService";

export async function callPoints(name, data = {}) {
  return callPiService(`/api/points/${encodeURIComponent(name)}`, data, {
    unavailableMessage: "The payment service is unavailable.",
  });
}

export function paymentError(error) {
  if (["permission-denied", "firestore/permission-denied"].includes(error?.code) && error?.name === "FirebaseError") {
    return "The app cannot load its payment connection. Ask the owner to check the payment service setup.";
  }
  if (error instanceof TypeError || error instanceof SyntaxError || error?.name === "AbortError" ||
      ["internal", "unavailable"].includes(error?.code)) {
    return "The payment server could not be reached. Ask the owner to check the Raspberry Pi and its internet connection. If you already sent money, do not pay again.";
  }
  return error?.message || "We could not complete this request. Please try again.";
}

export const PURCHASE_STATUS = {
  awaiting_payment: "Awaiting payment",
  pending: "Waiting for owner verification",
  approved: "Approved · points added",
  rejected: "Rejected",
};
