import { expect, test } from "@playwright/test";

const origin = "https://127.0.0.1:4174";
// All requests hit the canonical HTTP router and durable SQLite. No page.route mocks.
async function login(page, account = "operator") {
  await page.goto(origin);
  await page.locator("#login-email").fill(`${account}@example.com`);
  await page.locator("#login-password").fill("synthetic-p02-http-password-2026");
  await page.locator("#login-form button[type=submit]").click();
  await expect(page.locator("#authority-context")).toContainText("tenant-a");
}

test("five fiscal views show durable authorized state and explicit capability blocking", async ({page}) => {
  await login(page);
  for (const [label, expected] of [["Documentos", "DOC-a"], ["Emissões", "DOC-a"], ["Erros", "DOC-a"], ["Reconciliação", "DOC-a"]]) {
    await page.getByRole("button", {name: label, exact: true}).click();
    await expect(page.locator("#workspace")).toContainText(expected);
    await expect(page.locator("#workspace")).not.toContainText("DOC-b");
    await expect(page.locator("#workspace")).not.toContainText("DOC-other");
    await expect(page.locator("#workspace")).not.toContainText("PROTECTED_SYNTHETIC_RAW_CONTENT");
    await expect(page.locator("#workspace")).not.toContainText("LEGACY-UNSCOPED");
  }
  await page.getByRole("button", {name: "Capabilities", exact: true}).click();
  await expect(page.locator("#workspace")).toContainText("CAPABILITY_AUTHORITY_NOT_CONFIGURED");
  await expect(page.locator("#workspace")).not.toContainText("HOMOLOGATION_READY");
});

test("owner can select a permitted unit while operator cannot request another unit", async ({page}) => {
  await login(page, "owner");
  await page.getByRole("button", {name: "Documentos", exact: true}).click();
  await page.locator("#fiscal-unit-filter").selectOption("unit-b");
  await expect(page.locator("#workspace")).toContainText("DOC-b");
  await expect(page.locator("#workspace")).not.toContainText("DOC-a");
  await page.locator("#logout-action").click();
  await login(page);
  await page.getByRole("button", {name: "Documentos", exact: true}).click();
  await expect(page.locator("#fiscal-unit-filter option")).toHaveCount(1);
  const response = await page.request.get(`${origin}/v1/portal/surfaces/documents?unit_id=unit-b`);
  expect(response.status()).toBe(403);
});

test("retry after post-commit failure reuses intent and shows one durable reservation", async ({page}) => {
  await login(page);
  await page.getByRole("button", {name: "Emissões", exact: true}).click();
  await page.getByRole("button", {name: "Executar operação governada"}).click();
  await page.locator("#operation-payload").fill('{"document_kind":"nfe","synthetic_test":true}');
  const keys = [];
  page.on("request", (request) => {
    if (request.url().includes("/fiscal-intents/") && request.url().endsWith("/resume")) keys.push(request.headers()["idempotency-key"]);
  });
  await page.getByRole("button", {name: "Executar", exact: true}).click();
  await expect(page.locator("#operation-error")).toContainText("Synthetic response loss");
  await page.getByRole("button", {name: "Executar", exact: true}).click();
  await expect(page.locator("#operation-dialog")).not.toBeVisible();
  await expect(page.locator("#workspace")).toContainText("HTTP-RESERVATION-");
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).toBe(keys[1]);
  const response = await page.request.get(`${origin}/v1/portal/surfaces/issuances?unit_id=unit-a`);
  const body = await response.json();
  expect(body.rows.filter((row) => row.document_id?.startsWith("HTTP-RESERVATION-"))).toHaveLength(1);
  // This proves a reservation and replay, never SEFAZ/provider issuance or production.
});
