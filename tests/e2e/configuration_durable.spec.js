import { expect, test } from "@playwright/test";

const origin = "https://127.0.0.1:4174";

test("customer configuration views read canonical metadata without secrets or save claims", async ({page}) => {
  await page.goto(origin);
  await page.locator("#login-email").fill("owner@example.com");
  await page.locator("#login-password").fill("synthetic-p02-http-password-2026");
  await page.locator("#login-form button[type=submit]").click();
  await expect(page.locator("#authority-context")).toContainText("tenant-a");
  for (const [label, identifier] of [
    ["Certificados", "ref:synthetic-a-certificate"],
    ["Providers", "binding-a"],
    ["Webhooks", "events-a"],
    ["Integrações", "module-a"],
    ["Configurações", "policy-a"],
  ]) {
    await page.getByRole("button", {name: label, exact: true}).click();
    await expect(page.locator("#workspace")).toContainText(identifier);
    await expect(page.locator("#workspace")).toContainText("Alterações aguardam");
    await expect(page.locator("#workspace")).not.toContainText("SYNTHETIC_QUERY_MUST_NOT_ESCAPE");
    await expect(page.locator("#workspace")).not.toContainText("callback.example.invalid");
    await expect(page.getByRole("button", {name: "Salvar", exact: true})).toHaveCount(0);
  }
  await page.locator("#fiscal-unit-filter").selectOption("unit-b");
  await expect(page.locator("#workspace")).toContainText("policy-b");
  await expect(page.locator("#workspace")).not.toContainText("policy-a");
});
