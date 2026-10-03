import assert from "node:assert/strict";
import test from "node:test";

import { createRegistrationEmailValidation } from "./registrationEmailValidation.js";

test("editing a validated email clears success and requires a new remote check", async () => {
  let email = "first@example.com";
  const checkedAddresses = [];
  const validation = createRegistrationEmailValidation({
    getEmail: () => email,
    isValidFormat: (value) => value.includes("@"),
    request: async (value) => {
      checkedAddresses.push(value);
      return { valid: true, status: "valid" };
    },
  });

  assert.equal(await validation.check(), true);
  assert.equal(validation.status.value, "valid");
  assert.equal(await validation.check(), true);
  assert.deepEqual(checkedAddresses, ["first@example.com"]);

  email = "second@example.com";
  validation.handleInput({ target: { value: email } });
  assert.equal(validation.status.value, "");
  assert.equal(validation.checking.value, false);

  assert.equal(await validation.check(), true);
  assert.deepEqual(checkedAddresses, ["first@example.com", "second@example.com"]);
  assert.equal(validation.status.value, "valid");
});

test("a stale success cannot validate an edited address", async () => {
  let email = "first@example.com";
  const pending = [];
  const validation = createRegistrationEmailValidation({
    getEmail: () => email,
    isValidFormat: (value) => value.includes("@"),
    request: (value) =>
      new Promise((resolve) => {
        pending.push({ email: value, resolve });
      }),
  });

  const firstCheck = validation.check();
  email = "second@example.com";
  validation.handleInput({ target: { value: email } });
  const secondCheck = validation.check();
  assert.deepEqual(
    pending.map((entry) => entry.email),
    ["first@example.com", "second@example.com"],
  );

  pending[0].resolve({ valid: true, status: "valid" });
  assert.equal(await firstCheck, false);
  assert.equal(validation.status.value, "checking");

  pending[1].resolve({ valid: false, status: "invalid" });
  assert.equal(await secondCheck, false);
  assert.equal(validation.status.value, "invalid");
});

test("rate limiting has its own status and waits before retrying", async () => {
  let currentTime = 1_000;
  let requests = 0;
  const validation = createRegistrationEmailValidation({
    getEmail: () => "patient@example.com",
    isValidFormat: () => true,
    now: () => currentTime,
    request: async () => {
      requests += 1;
      if (requests === 1) {
        throw Object.assign(new Error("Too many requests"), {
          status: 429,
          data: { retry_after: 30 },
        });
      }
      return { valid: true, status: "valid" };
    },
  });

  assert.equal(await validation.check(), false);
  assert.equal(validation.status.value, "rate_limited");
  assert.equal(await validation.check(), false);
  assert.equal(requests, 1);

  currentTime += 30_000;
  assert.equal(await validation.check(), true);
  assert.equal(requests, 2);
  assert.equal(validation.status.value, "valid");
});

test("a provider typo suggestion remains available on an invalid result", async () => {
  const validation = createRegistrationEmailValidation({
    getEmail: () => "patient@gmial.com",
    isValidFormat: () => true,
    request: async () => ({
      valid: false,
      status: "invalid",
      suggested_email: "patient@gmail.com",
    }),
  });

  assert.equal(await validation.check(), false);
  assert.equal(validation.status.value, "invalid");
  assert.equal(validation.suggestedEmail.value, "patient@gmail.com");
});
