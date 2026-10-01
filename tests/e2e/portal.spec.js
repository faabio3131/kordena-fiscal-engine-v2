import { expect, test } from "@playwright/test";

test("authenticated portal loads governed tenant context and real surface", async ({ page, context }) => {
  await page.route("**/v1/portal/bootstrap", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        product: "FM NFCORE",
        version: "1.0",
        tenant_id: "tenant-e2e",
        unit_ids: ["unit-a"],
        role: "owner",
        permissions: ["portal.read", "document.query", "document.issue"],
        supported_documents: ["nfe", "nfce", "nfse"],
        projection: { production_state: "BLOCKED_EXTERNAL", readiness: "EVIDENCE_REQUIRED" },
      }),
    });
  });

  await page.route("**/v1/portal/surfaces/documents", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        surface: "documents",
        rows: [{ document_id: "DOC-E2E-1", kind: "NF-e", status: "AUTHORIZED" }],
      }),
    });
  });

  await context.addCookies([
    { name: "nfcore_session", value: "opaque-session", domain: "127.0.0.1", path: "/" },
    { name: "nfcore_csrf", value: "csrf-e2e", domain: "127.0.0.1", path: "/" },
  ]);

  await page.goto("/");
  await expect(page.getByText("tenant-e2e · owner")).toBeVisible();
  await expect(page.locator("#critical-state-title")).toHaveText("BLOCKED_EXTERNAL");
  await page.getByRole("button", { name: "Documentos" }).click();
  await expect(page.getByText("DOC-E2E-1")).toBeVisible();
  await expect(page.getByText("AUTHORIZED")).toBeVisible();
});

test("governed mutation sends csrf and idempotency proof", async ({ page, context }) => {
  await page.route("**/v1/portal/bootstrap", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        product: "FM NFCORE",
        version: "1.0",
        tenant_id: "tenant-e2e",
        unit_ids: ["unit-a"],
        role: "owner",
        permissions: ["portal.read", "document.query", "document.issue"],
        supported_documents: ["nfe", "nfce", "nfse"],
        projection: { production_state: "BLOCKED_EXTERNAL" },
      }),
    });
  });
  await page.route("**/v1/portal/surfaces/issuances", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ surface: "issuances", rows: [] }) });
  });

  let seenCsrf = "";
  let seenIdempotency = "";
  await page.route("**/v1/portal/operations/issueFiscalDocument", async (route) => {
    seenCsrf = route.request().headers()["x-csrf-token"] || "";
    seenIdempotency = route.request().headers()["idempotency-key"] || "";
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ACCEPTED" }) });
  });

  await context.addCookies([
    { name: "nfcore_session", value: "opaque-session", domain: "127.0.0.1", path: "/" },
    { name: "nfcore_csrf", value: "csrf-e2e", domain: "127.0.0.1", path: "/" },
  ]);

  await page.goto("/");
  await page.getByRole("button", { name: "Emissões" }).click();
  await page.getByRole("button", { name: "Executar operação governada" }).click();
  await page.locator("#operation-unit").fill("unit-a");
  await page.locator("#operation-payload").fill('{"document":{"model":"55"}}');
  await page.getByRole("button", { name: "Executar", exact: true }).click();

  expect(seenCsrf).toBe("csrf-e2e");
  expect(seenIdempotency.length).toBeGreaterThan(10);
});

test("activation fragment completes password setup without keeping token in URL", async ({ page }) => {
  let submittedToken = "";

  await page.route("**/v1/portal/bootstrap", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: { message: "Authentication required" } }),
    });
  });
  await page.route("**/v1/auth/password-reset/complete", async (route) => {
    const payload = route.request().postDataJSON();
    submittedToken = payload.reset_token || "";
    await route.fulfill({ status: 204, body: "" });
  });

  await page.goto("/#token=synthetic-fragment-reset-token");
  await expect(page.locator("#password-reset-complete-form")).toBeVisible();

  await page.locator("#password-reset-new-password").fill("Strong-password-2026");
  await page.getByRole("button", { name: "Alterar senha" }).click();

  expect(submittedToken).toBe("synthetic-fragment-reset-token");
  await expect(page).not.toHaveURL(/token=/);
  await expect(page.getByText("Senha alterada. Entre novamente com a nova senha.")).toBeVisible();
});


test("activation shows actionable pt-BR message for an unusable reset token", async ({ page }) => {
  await page.route("**/v1/portal/bootstrap", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: { message: "Authentication required" } }),
    });
  });
  await page.route("**/v1/auth/password-reset/complete", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        detail: {
          code: "PASSWORD_RESET_NOT_USABLE",
          message: "Password reset is not usable",
        },
      }),
    });
  });

  await page.goto("/#token=obsolete-reset-token");
  await expect(page.getByText(/12 a 1024 caracteres/)).toBeVisible();
  await page.locator("#password-reset-new-password").fill("G7!mQ2#vR9$kT4-xP8@cL6");
  await page.getByRole("button", { name: "Alterar senha" }).click();

  await expect(
    page.getByText(
      "Este link de recuperação não é mais válido. Solicite um novo link e use somente o e-mail mais recente.",
    ),
  ).toBeVisible();
});
