import assert from "node:assert/strict";
import test from "node:test";

import {
  internationalRegistrationMobile,
  localMobileFromPaste,
  MOBILE_LENGTH_MESSAGE,
  MOBILE_PREFIX_MESSAGE,
  registrationMobileError,
} from "./registrationMobile.js";

test("converts the three full Philippine paste formats to ten local digits", () => {
  for (const value of ["09171234567", "+639171234567", "639171234567", "9171234567"]) {
    assert.equal(localMobileFromPaste(value), "9171234567");
  }
  assert.equal(localMobileFromPaste("917 123 4567"), "9171234567");
});

test("does not turn malformed pasted text into a valid number", () => {
  for (const value of [
    "abc9171234567",
    "+6309171234567",
    "8171234567",
    "917123456",
    "91712345678",
    "09+171234567",
  ]) {
    assert.equal(localMobileFromPaste(value), null);
  }
});

test("accepts exactly ten local digits beginning with nine and submits +639", () => {
  for (const value of ["9171234567", "9451234567", "9987654321"]) {
    assert.equal(registrationMobileError(value), "");
    assert.equal(internationalRegistrationMobile(value), `+63${value}`);
  }
});

test("rejects missing, short, and non-nine mobile input before submission", () => {
  assert.equal(registrationMobileError(""), MOBILE_LENGTH_MESSAGE);
  assert.equal(registrationMobileError("917123456"), MOBILE_LENGTH_MESSAGE);
  assert.equal(registrationMobileError("8171234567"), MOBILE_PREFIX_MESSAGE);
  assert.equal(registrationMobileError("09171234567"), MOBILE_PREFIX_MESSAGE);
  assert.throws(() => internationalRegistrationMobile("8171234567"), {
    message: MOBILE_PREFIX_MESSAGE,
  });
});
