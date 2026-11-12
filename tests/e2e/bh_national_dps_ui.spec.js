import {expect, test} from "@playwright/test";

const fullRights = [
  "portal.read", "document.query", "document.issue",
  "configuration.write",
];

async function openBh(page, context, permissions) {
  await page.route("**/v1/portal/bootstrap", route => route.fulfill({json: {
    product: "FM NFCORE", version: "1.0", tenant_id: "tenant-bh",
    unit_ids: ["unit-bh"], role: "owner", permissions,
    supported_documents: ["nfse"],
    projection: {
      production_state: "BLOCKED_EXTERNAL",
      configured_fiscal_operations: ["issueFiscalDocument", "reconcileFiscalOperation"],
      authorized_units: [{
        unit_id: "unit-bh", display_name: "Belo Horizonte Synthetic",
        environments: ["homologation"],
      }],
    },
  }}));
  await page.route("**/v1/portal/surfaces/**", route => route.fulfill({
    json: {surface: "issuances", rows: []},
  }));
  await page.route("**/v1/portal/fiscal-intents?**", route => route.fulfill({
    json: {rows: []},
  }));
  await context.addCookies([
    {name: "nfcore_session", value: "synthetic", domain: "127.0.0.1", path: "/"},
    {name: "nfcore_csrf", value: "bh-synthetic-csrf", domain: "127.0.0.1", path: "/"},
  ]);
  await page.goto("/");
  await page.getByRole("button", {name: "Emissões", exact: true}).click();
}

test("BH National DPS preparation requires approved fiscal classification and scoped session", async ({page, context}) => {
  await openBh(page, context, fullRights);
  const form = page.locator("#bh-nfse-preparation");
  await expect(form).toBeVisible();

  const values = {
    source_id: "bh-approved-order-1",
    competence_date: "2026-11-12", service_code: "0107",
    national_taxation_code: "010701", municipal_taxation_detail: "001",
    nbs_code: "123456789", description: "Synthetic service reviewed by accountant",
    gross_amount: "100.00", deduction_amount: "0.00",
    iss_rate_fraction: "0.0300",
    rule_reference: "urn:nfcore:bh:reviewed:2026",
    rule_version: "1", dps_series: "1",
  };
  for (const [key, value] of Object.entries(values)) {
    await form.locator('input[name="' + key + '"]').fill(value);
  }
  await form.locator("select").first().selectOption("false");
  await form.locator("select").nth(1).selectOption("0");
  await form.locator('input[type="checkbox"]').check();

  const recorded = [];
  await page.route("**/v1/portal/operations/prepareBhNfse", route => {
    const request = route.request();
    expect(request.headers()["x-csrf-token"]).toBe("bh-synthetic-csrf");
    expect(request.headers()["idempotency-key"]).toBeTruthy();
    const payload = request.postDataJSON();
    recorded.push(payload);
    return route.fulfill({json: {
      document_id: "bh-prepared-1", status: "ready_to_transmit",
      dps_number: 1, dps_series: 1, transmitted: false,
      fiscal_authorization: "not_inferred_from_preparation",
    }});
  });
  await form.getByRole("button", {name: "Preparar DPS em homologação"}).click();
  await expect(form.getByRole("status")).toContainText("NÃO é autorização fiscal");
  expect(recorded).toHaveLength(1);
  expect(recorded[0]).toMatchObject({
    unit_id: "unit-bh", environment: "homologation",
    municipal_taxation_detail: "001", nbs_code: "123456789",
    special_tax_regime: "0", fiscal_review_approved: true,
    iss_withheld: false, rule_version: 1, dps_series: 1,
  });
  expect(recorded[0]).not.toHaveProperty("tenant_id");
  expect(recorded[0]).not.toHaveProperty("certificate");
  expect(recorded[0]).not.toHaveProperty("provider_id");
});

test("BH preparation is not visible without both configuration and issuance authority", async ({page, context}) => {
  await openBh(page, context, ["portal.read", "document.query", "configuration.write"]);
  await expect(page.locator("#bh-nfse-preparation")).toHaveCount(0);
});
