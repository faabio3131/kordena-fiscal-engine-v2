import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../../portal/index.html", import.meta.url), "utf8");
const script = await readFile(new URL("../../portal/app.js", import.meta.url), "utf8");


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
});


test("portal keeps accessible login and governed operation surfaces", () => {
  assert.match(html, /id="login-form"/);
  assert.match(html, /autocomplete="username"/);
  assert.match(html, /autocomplete="current-password"/);
  assert.match(html, /aria-labelledby="operation-dialog-title"/);
  assert.match(html, /role="alert"/);
});
