import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../../portal/index.html", import.meta.url), "utf8");
const script = await readFile(new URL("../../portal/app.js", import.meta.url), "utf8");
const styles = await readFile(new URL("../../portal/styles.css", import.meta.url), "utf8");
const runtimeStyles = await readFile(new URL("../../portal/runtime.css", import.meta.url), "utf8");


test("portal uses authenticated backend contracts", () => {
  assert.match(script, /\/v1\/auth\/login/);
  assert.match(script, /\/v1\/portal\/bootstrap/);
  assert.match(script, /\/v1\/portal\/surfaces\//);
  assert.match(script, /\/v1\/portal\/operations\//);
  assert.match(script, /credentials: "same-origin"/);
});


test("browser never supplies tenant or role authority", () => {
  assert.doesNotMatch(script, /X-FM-Tenant-Id/);
  assert.doesNotMatch(script, /X-FM-Unit-Id/);
  assert.doesNotMatch(script, /localStorage/);
  assert.doesNotMatch(script, /sessionStorage/);
  assert.match(html, /O navegador nunca é autoridade/);
});


test("mutations carry CSRF and idempotency controls", () => {
  assert.match(script, /X-CSRF-Token/);
  assert.match(script, /Idempotency-Key/);
  assert.match(script, /crypto\.randomUUID\(\)/);
  assert.match(script, /onboardUnit/);
});


test("portal keeps accessible login and governed operation surfaces", () => {
  assert.match(html, /id="login-form"/);
  assert.match(html, /autocomplete="username"/);
  assert.match(html, /autocomplete="current-password"/);
  assert.match(html, /aria-labelledby="operation-dialog-title"/);
  assert.match(html, /role="alert"/);
});


test("commercial recovery is browser-usable without exposing reset token on request", () => {
  assert.match(html, /id="forgot-password-action"/);
  assert.match(html, /id="password-reset-request-form"/);
  assert.match(html, /autocomplete="new-password"/);
  assert.match(script, /\/v1\/auth\/password-reset\/request/);
  assert.match(script, /\/v1\/auth\/password-reset\/complete/);
  assert.match(script, /reset_token/);
  assert.doesNotMatch(script, /console\.log/);
});


test("navigation is constrained by backend-declared durable surfaces", () => {
  assert.match(script, /available_surfaces/);
  assert.match(script, /availableSurfaces\(\)/);
  assert.match(script, /allowed === null \|\| allowed\.has\(id\)/);
});


test("premium design system preserves responsive and accessibility contracts", () => {
  assert.match(styles, /--brand-primary:/);
  assert.match(styles, /--brand-cyan:/);
  assert.match(styles, /--radius-lg:/);
  assert.match(styles, /@media \(max-width: 760px\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(runtimeStyles, /:focus-visible/);
  assert.match(runtimeStyles, /button:disabled/);
  assert.match(runtimeStyles, /prefers-contrast: more/);
  assert.match(runtimeStyles, /prefers-reduced-motion: reduce/);
});
