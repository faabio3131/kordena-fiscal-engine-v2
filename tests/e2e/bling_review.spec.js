import { expect, test } from "@playwright/test";

test("Bling review pins a snapshot, escapes supplier text and requires explicit approval", async ({ page, context }) => {
  await context.addCookies([{name: "nfcore_csrf", value: "review-csrf", domain: "127.0.0.1", path: "/"}]);
  await page.route("**/v1/portal/bootstrap", route => route.fulfill({json: {
    tenant_id: "synthetic", unit_ids: ["unit"], role: "owner",
    permissions: ["portal.read", "integration.manage", "document.issue"],
    supported_documents: ["nfe"], projection: {available_surfaces: ["integrations"]},
  }}));
  await page.route("**/v1/portal/surfaces/integrations*", route => route.fulfill({json: {rows: []}}));
  let selected = "old";
  let approved = false;
  await page.route("**/v1/portal/integrations/bling/orders/9001**", route => {
    const request = route.request();
    if (request.method() === "POST") {
      expect(request.headers()["x-csrf-token"]).toBe("review-csrf");
      if (request.url().endsWith("select-snapshot")) {
        expect(request.postDataJSON()).toEqual({snapshot_sha256: "new"}); selected = "new";
      } else {
        expect(request.postDataJSON()).toEqual({snapshot_sha256: "new", document_id: "prepared-1"}); approved = true;
      }
      return route.fulfill({json: {order: {state: approved ? "queued" : "review_required"}}});
    }
    return route.fulfill({json: {order: {state: approved ? "queued" : "review_required", snapshot_sha256: selected,
      changed_snapshot_sha256: selected === "old" ? "new" : null, document_id: approved ? "prepared-1" : null},
    snapshots: [selected, ...(selected === "old" ? ["new"] : [])].map(sha256 => ({sha256, content: {raw: {nome: "<img src=x onerror=alert(1)>"}}}))}});
  });
  await page.goto("/");
  await page.getByRole("button", {name: "Integrações", exact: true}).click();
  await page.getByLabel("Número interno do pedido no Bling").fill("9001");
  await page.getByRole("button", {name: "Consultar pedido"}).click();
  await page.getByText("Atualização aguardando revisão", {exact: true}).click();
  await expect(page.locator("details img")).toHaveCount(0);
  await page.getByRole("button", {name: "Selecionar esta atualização"}).click();
  await expect(page.getByLabel("Documento fiscal preparado no NFCore")).toBeVisible();
  await page.getByRole("button", {name: "Aprovar envio"}).click();
  expect(approved).toBe(false);
  await page.getByLabel("Documento fiscal preparado no NFCore").fill("prepared-1");
  await page.getByLabel("Revisei o pedido e a correspondência com o documento fiscal preparado.").check();
  await page.getByRole("button", {name: "Aprovar envio"}).click();
  await expect(page.getByText("Situação: queued", {exact: true})).toBeVisible();
  expect(approved).toBe(true);
});

test("native preparation reviews recipient and posts only scoped fiscal facts", async ({page, context}) => {
  await context.addCookies([{name: "nfcore_csrf", value: "native-csrf", domain: "127.0.0.1", path: "/"}]);
  await page.route("**/v1/portal/bootstrap", route => route.fulfill({json: {
    tenant_id: "synthetic", unit_ids: ["unit"], role: "owner",
    permissions: ["portal.read", "integration.manage", "document.issue"],
    supported_documents: ["nfe"], projection: {available_surfaces: ["integrations"]},
  }}));
  await page.route("**/v1/portal/surfaces/integrations*", route => route.fulfill({json: {rows: []}}));
  let queued = false;
  await page.route("**/v1/portal/integrations/bling/orders/123**", route => {
    if (route.request().method() === "POST") {
      expect(route.request().url()).toMatch(/\/prepare$/);
      expect(route.request().headers()["x-csrf-token"]).toBe("native-csrf");
      const body = route.request().postDataJSON();
      expect(Object.keys(body).sort()).toEqual(["issued_at", "policy_sha256", "recipient", "snapshot_sha256"]);
      expect(body.recipient.document).toBe("12345678000195");
      expect(body.recipient.ie_indicator).toBe(9);
      expect(body.recipient.final_consumer).toBe(true);
      expect(body.policy_sha256).toBe("policy-hash");
      queued = true;
      return route.fulfill({json: {document_id: "native-doc", state: "queued"}});
    }
    return route.fulfill({json: {
      order: {state: queued ? "queued" : "review_required", snapshot_sha256: "snapshot-hash", document_id: queued ? "native-doc" : null},
      snapshots: [{sha256: "snapshot-hash", content: {raw: {contato: {nome: "Synthetic buyer", numeroDocumento: "12345678000195"}}}}],
      preparation: {configured: true, policy_id: "synthetic", version: 1, sha256: "policy-hash", issued_at: "2026-11-09T00:00:00+00:00"},
    }});
  });
  await page.goto("/");
  await page.getByRole("button", {name: "Integrações", exact: true}).click();
  await page.getByLabel("Número interno do pedido no Bling").fill("123");
  await page.getByRole("button", {name: "Consultar pedido"}).click();
  await page.getByRole("button", {name: "Preparar e enviar NF-e"}).click();
  expect(queued).toBe(false);
  for (const [label, value] of [["Logradouro", "Rua Sintetica"], ["Número do endereço", "1"], ["Bairro", "Centro"], ["Município", "Sao Paulo"], ["Código IBGE do município", "3550308"], ["UF", "SP"], ["CEP", "01001000"]]) {
    await page.getByLabel(label, {exact: true}).fill(value);
  }
  await page.getByLabel("Condição da inscrição estadual").selectOption("9");
  await page.getByLabel("Consumidor final", {exact: true}).selectOption("true");
  await page.getByLabel("Revisei o pedido, o destinatário e a política fiscal indicada.").check();
  await page.getByRole("button", {name: "Preparar e enviar NF-e"}).click();
  await expect(page.getByText("Situação: queued", {exact: true})).toBeVisible();
  expect(queued).toBe(true);
});
