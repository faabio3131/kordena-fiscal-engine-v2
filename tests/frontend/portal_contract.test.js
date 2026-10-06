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
  assert.match(html, /minlength="12"/);
  assert.match(html, /maxlength="1024"/);
  assert.match(html, /aria-describedby="password-policy"/);
  assert.match(html, /gerenciadores de senha são aceitas/);
  assert.match(script, /PASSWORD_POLICY_INVALID/);
  assert.match(script, /PASSWORD_RESET_NOT_USABLE/);
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


test("platform pricing administration is backend-authorized and zero-code", () => {
  assert.match(script, /pricing-admin/);
  assert.match(script, /\/v1\/admin\/pricing/);
  assert.match(script, /expected_version/);
  assert.match(script, /X-CSRF-Token/);
  assert.match(script, /platform_admin/);
  assert.match(script, /Sem preço comercial publicado|UNPRICED/);
  assert.doesNotMatch(script, /base_amount\s*:\s*["']\d/);
});


test("commercial release governance is explicit, human-controlled and separated from checkout", () => {
  assert.match(script, /commercial-release/);
  assert.match(script, /\/v1\/admin\/commercial-release/);
  assert.match(script, /commercial_approved/);
  assert.match(script, /human_decision_reference/);
  assert.match(script, /COMMERCIAL_APPROVED nunca é inferido/);
  assert.match(script, /Checkout e produção fiscal permanecem autoridades separadas/);
});


test("Cakto checkout administration reuses governed bindings without secret material", () => {
  assert.match(script, /checkout-admin/);
  assert.match(script, /\/v1\/admin\/checkout\/cakto/);
  assert.match(script, /cakto:\/\/PRODUCT_ID\/OFFER_ID/);
  assert.match(script, /X-CSRF-Token/);
  assert.match(script, /Client secret, token e webhook secret nunca pertencem/);
  assert.doesNotMatch(script, /client_secret\s*[:=]/i);
});

test("activation delivery consumes the reset token from the URL fragment", () => {
  assert.match(script, /window\.location\.hash/);
  assert.match(script, /fragment\.get\("token"\)/);
  assert.match(script, /fragment\.delete\("token"\)/);
});

test("customer configuration forms use existing portal commands and distinguish approval from delivery", () => {
  for (const operation of ["configureCertificates", "configureProviders", "configureWebhooks", "configureIntegrations", "configureSettings"]) assert.ok(script.includes(operation));
  assert.match(script, /customer_configuration_operations/);
  assert.match(script, /customer-configuration-form/);
  assert.match(script, /Verificação operacional não confirmada/);
  assert.match(script, /Solicitar entrega após aprovação da plataforma/);
  assert.match(script, /egress-decision-form/);
  assert.match(script, /if \(!bootstrapState\?\.platform_admin\) return/);
});
