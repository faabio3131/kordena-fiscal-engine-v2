import { expect, test } from "@playwright/test";

test("Bling operator can register a unit-bound installation through the canonical portal", async ({ page, context }) => {
  await context.addCookies([{name: "nfcore_csrf", value: "setup-csrf", domain: "127.0.0.1", path: "/"}]);
  await page.route("**/v1/portal/bootstrap", route => route.fulfill({json: {
    tenant_id: "tenant", unit_ids: ["unit"], role: "owner",
    permissions: ["portal.read", "integration.manage", "document.issue"],
    projection: {available_surfaces: ["integrations"],
      authorized_units: [{unit_id: "unit", display_name: "Unidade", environments: ["homologation"]}]},
  }}));
  await page.route("**/v1/portal/surfaces/integrations*", route => route.fulfill({json: {rows: []}}));
  await page.route("**/v1/portal/integrations/bling/bindings/available*", route =>
    route.fulfill({json: {rows: [{binding_id: "binding-allowed", unit_id: "unit"}], next_offset: null}}));
  let created = false;
  await page.route("**/v1/portal/integrations/bling/installations/available*", route =>
    route.fulfill({json: {rows: created ? [{
      installation_id: "b".repeat(32), company_id: "company-1",
      revision: 1, state: "not_configured",
    }] : [], next_cursor: null}}));
  await page.route("**/v1/portal/integrations/bling/installations", route => {
    const request = route.request();
    expect(request.method()).toBe("POST");
    expect(request.headers()["x-csrf-token"]).toBe("setup-csrf");
    expect(request.postDataJSON()).toEqual({
      binding_id: "binding-allowed", company_id: "company-1",
    });
    created = true;
    return route.fulfill({status: 201, json: {installation_id: "b".repeat(32), state: "not_configured"}});
  });
  await page.route("**/v1/portal/integrations/bling/installations/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/available")) return route.fallback();
    if (url.pathname.endsWith("/orders")) return route.fulfill({json: {rows: [], next_cursor: null}});
    if (url.pathname.endsWith("/jobs")) return route.fulfill({json: {rows: []}});
    if (url.pathname.endsWith("/metrics")) return route.fulfill({json: {
      sample_limit: 100, partial: false, order_states: {}, job_states: {}, has_dead_letter: false,
    }});
    return route.fulfill({status: 404, json: {code: "NOT_FOUND"}});
  });
  await page.goto("/");
  await page.getByRole("button", {name: "Integrações", exact: true}).click();
  await expect(page.getByText(/Nenhuma empresa Bling cadastrada/)).toBeVisible();
  await page.getByLabel("Vínculo fiscal Bling da unidade").selectOption("binding-allowed");
  await page.getByLabel("ID da empresa no Bling").fill("company-1");
  await page.getByRole("button", {name: "Cadastrar empresa Bling"}).click();
  await expect(page.getByText(/Empresa cadastrada/)).toBeVisible();
  await expect(page.getByRole("button", {name: "Conectar / reautorizar no Bling"})).toBeEnabled();
  expect(created).toBe(true);
});

test("Bling operator sets per-installation status mapping with revision and CSRF", async ({ page, context }) => {
  await context.addCookies([{name: "nfcore_csrf", value: "map-csrf", domain: "127.0.0.1", path: "/"}]);
  await page.route("**/v1/portal/bootstrap", route => route.fulfill({json: {
    tenant_id: "tenant", unit_ids: ["unit"], role: "owner",
    permissions: ["portal.read", "integration.manage", "document.issue"],
    projection: {available_surfaces: ["integrations"],
      authorized_units: [{unit_id: "unit", display_name: "Unidade", environments: ["homologation"]}]},
  }}));
  await page.route("**/v1/portal/surfaces/integrations*", route => route.fulfill({json: {rows: []}}));
  await page.route("**/v1/portal/integrations/bling/bindings/available*", route =>
    route.fulfill({json: {rows: [{binding_id: "binding-allowed", unit_id: "unit"}]}}));
  let revision = 8;
  await page.route("**/v1/portal/integrations/bling/installations/available*", route =>
    route.fulfill({json: {rows: [{
      installation_id: "c".repeat(32), company_id: "company-1", revision, state: "connected",
    }]}}));
  let changed = false;
  await page.route("**/v1/portal/integrations/bling/installations/**", route => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname.endsWith("/available")) return route.fallback();
    if (url.pathname.endsWith("/status-mapping")) {
      expect(req.headers()["x-csrf-token"]).toBe("map-csrf");
      expect(req.postDataJSON()).toEqual({
        authorized_status_id: 100, rejected_status_id: 200, expected_revision: 8,
      });
      revision = 9; changed = true;
      return route.fulfill({json: {installation_id: "c".repeat(32), revision: 9}});
    }
    if (url.pathname.endsWith("/orders")) return route.fulfill({json: {rows: [], next_cursor: null}});
    if (url.pathname.endsWith("/jobs")) return route.fulfill({json: {rows: []}});
    if (url.pathname.endsWith("/metrics")) return route.fulfill({json: {
      sample_limit: 100, partial: false, order_states: {}, job_states: {}, has_dead_letter: false,
    }});
    return route.fulfill({status: 404, json: {code: "NOT_FOUND"}});
  });
  await page.goto("/");
  await page.getByRole("button", {name: "Integrações", exact: true}).click();
  await expect(page.getByLabel("URL do webhook Bling")).toHaveValue(
    `http://127.0.0.1:8081/webhooks/bling/installations/${"c".repeat(32)}`,
  );
  await expect(page.getByRole("button", {name: "Salvar mapeamento de status"})).toBeEnabled();
  await page.getByLabel("ID do status autorizado no Bling").fill("100");
  await page.getByLabel("ID do status rejeitado no Bling").fill("200");
  await page.getByRole("button", {name: "Salvar mapeamento de status"}).click();
  await expect(page.getByText(/Mapeamento salvo/)).toBeVisible();
  expect(changed).toBe(true);
});

test("Bling operator provisions an exact fiscal binding when unit is new", async ({ page, context }) => {
  await context.addCookies([{name: "nfcore_csrf", value: "binding-csrf", domain: "127.0.0.1", path: "/"}]);
  await page.route("**/v1/portal/bootstrap", route => route.fulfill({json: {
    tenant_id: "tenant", role: "owner", unit_ids: ["unit"],
    permissions: ["portal.read", "integration.manage", "document.issue"],
    projection: {available_surfaces: ["integrations"],
      authorized_units: [{unit_id: "unit", display_name: "Unidade", environments: ["homologation"]}]},
  }}));
  await page.route("**/v1/portal/surfaces/integrations*", route => route.fulfill({json: {rows: []}}));
  let bound = false;
  await page.route("**/v1/portal/integrations/bling/bindings/available*", route =>
    route.fulfill({json: {rows: bound ? [{binding_id: "new-binding", unit_id: "unit"}] : []}}));
  await page.route("**/v1/portal/integrations/bling/bindings", route => {
    const request = route.request();
    expect(request.headers()["x-csrf-token"]).toBe("binding-csrf");
    expect(request.postDataJSON()).toEqual({unit_id: "unit"});
    bound = true;
    return route.fulfill({status: 201, json: {binding_id: "new-binding", created: true}});
  });
  await page.route("**/v1/portal/integrations/bling/installations/available*", route =>
    route.fulfill({json: {rows: []}}));
  await page.goto("/");
  await page.getByRole("button", {name: "Integrações", exact: true}).click();
  await expect(page.getByRole("button", {name: "Cadastrar empresa Bling"})).toBeDisabled();
  await page.getByRole("button", {name: "Criar vínculo fiscal Bling"}).click();
  await expect(page.getByText(/Vínculo fiscal criado/)).toBeVisible();
  await expect(page.getByRole("button", {name: "Cadastrar empresa Bling"})).toBeEnabled();
  expect(bound).toBe(true);
});
