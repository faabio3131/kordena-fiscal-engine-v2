import { expect, test } from "@playwright/test";

const origin = "https://127.0.0.1:4174";
async function login(page, name = "operator") {
  await page.goto(origin);
  await page.locator("#login-email").fill(`${name}@example.com`);
  await page.locator("#login-password").fill("synthetic-p02-http-password-2026");
  await page.locator("#login-form button[type=submit]").click();
  await expect(page.locator("#authority-context")).toContainText("tenant-a");
}

test("inutilization has typed fields and retries the same internal durable intent", async ({page}) => {
  // Real loopback router/session/CSRF/SQLite; injected outbox handler never dispatches.
  await login(page);
  await page.getByRole("button", {name: "Inutilização", exact: true}).click();
  await page.locator("#inutilization-model").selectOption("65");
  await page.locator("#inutilization-series").fill("7");
  await page.locator("#inutilization-first_number").fill("301");
  await page.locator("#inutilization-last_number").fill("303");
  await page.locator("#inutilization-justification").fill("Justificativa sintetica da jornada interna");
  await page.locator("#inutilization-confirm").check();
  const keys = [], bodies = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/operations/inutilizeFiscalRange")) {
      keys.push(request.headers()["idempotency-key"]); bodies.push(request.postDataJSON());
    }
  });
  await page.getByRole("button", {name: "Solicitar inutilização", exact: true}).click();
  await expect(page.locator("#inutilization-result")).toContainText("Synthetic response loss");
  // Changing a pending request cannot silently create another intent.
  await page.locator("#inutilization-last_number").fill("304");
  await page.getByRole("button", {name: "Solicitar inutilização", exact: true}).click();
  await expect(page.locator("#inutilization-result")).toContainText("outro conteúdo");
  expect(keys).toHaveLength(1);
  await page.locator("#inutilization-last_number").fill("303");
  await page.getByRole("button", {name: "Solicitar inutilização", exact: true}).click();
  await expect(page.locator("#inutilization-result")).toContainText("Resposta recebida do executor");
  expect(keys).toHaveLength(2); expect(keys[0]).toBeTruthy(); expect(keys[0]).toBe(keys[1]);
  expect(bodies[0]).toEqual(bodies[1]); expect(bodies[0].model).toBe(65);
  expect(bodies[0].tenant_id).toBeUndefined();
  await page.getByRole("button", {name: "Atualizar acompanhamento"}).click();
  await expect(page.locator("#workspace")).toContainText("not_inferred_from_outbox");
  await expect(page.locator("#workspace")).not.toContainText("SYNTHETIC-INUTILIZATION-PROTOCOL");
  const response = await page.request.get(`${origin}/v1/portal/surfaces/inutilizations?unit_id=unit-a`);
  expect(response.status()).toBe(200);
  const rows = (await response.json()).rows;
  expect(rows).toHaveLength(1); expect(rows[0].status).toBe("pending");
  expect(JSON.stringify(rows)).not.toContain("Justificativa sintetica");
  expect(JSON.stringify(rows)).not.toContain("payload");
});

test("auditor cannot navigate or invoke inutilization and operator cannot switch unit", async ({page}) => {
  await login(page, "auditor");
  await expect(page.getByRole("button", {name: "Inutilização", exact: true})).toHaveCount(0);
  expect((await page.request.get(`${origin}/v1/portal/surfaces/inutilizations?unit_id=unit-a`)).status()).toBe(403);
  await page.locator("#logout-action").click();
  await login(page);
  await page.getByRole("button", {name: "Inutilização", exact: true}).click();
  await expect(page.locator("#fiscal-unit-filter option")).toHaveCount(1);
  expect((await page.request.get(`${origin}/v1/portal/surfaces/inutilizations?unit_id=unit-b`)).status()).toBe(403);
});
