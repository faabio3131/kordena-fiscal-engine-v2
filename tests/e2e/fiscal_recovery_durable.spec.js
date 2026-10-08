import {expect, test} from "@playwright/test";
import fs from "node:fs";

// Separate real loopback runtime/database to avoid sharing receipts with other journeys.
const origin = "https://127.0.0.1:4175";
async function login(page) {
  await page.goto(origin);
  await page.locator("#login-email").fill("operator@example.com");
  await page.locator("#login-password").fill("synthetic-p02-http-password-2026");
  await page.locator("#login-form button[type=submit]").click();
  await expect(page.locator("#authority-context")).toContainText("tenant-a");
}
async function fill(page, series) {
  await page.getByRole("button", {name:"Inutilização",exact:true}).click();
  await page.locator("#inutilization-series").fill(String(series));
  await page.locator("#inutilization-first_number").fill("901");
  await page.locator("#inutilization-last_number").fill("903");
  await page.locator("#inutilization-justification").fill("Justificativa sintetica de recuperacao interna");
  await page.locator("#inutilization-confirm").check();
}
function resumeButton(page,intent) {
  return page.locator(`[data-intent-id="${intent}"]`).getByRole("button",{name:"Retomar pedido original",exact:true});
}

test("reload after committed outbox and lost response recovers one original request",async({page})=>{
  await login(page); await fill(page,31);
  const receiptResponse = page.waitForResponse(r=>r.url().includes("/fiscal-intents/prepare/") && r.request().method()==="POST");
  const requests=[];
  page.on("request",r=>{if(r.url().includes("/fiscal-intents/") && r.url().endsWith("/resume")) requests.push(r);});
  await page.getByRole("button",{name:"Solicitar inutilização",exact:true}).click();
  const intent = (await (await receiptResponse).json()).intent_id;
  await expect(page.locator("#inutilization-result")).toContainText("Synthetic response loss");
  await page.reload(); await fill(page,31);
  await resumeButton(page,intent).click();
  await page.getByRole("button",{name:"Solicitar inutilização",exact:true}).click();
  await expect(page.locator("#inutilization-result")).toContainText("Resposta recebida do executor");
  await expect(page.locator(`[data-intent-id="${intent}"]`)).toHaveAttribute("data-intent-state","recorded");
  await expect(page.locator("#fiscal-recovery")).toContainText("Resposta registrada");
  expect(requests).toHaveLength(2);
  expect(requests[0].postDataJSON()).toEqual(requests[1].postDataJSON());
  const receipts=(await (await page.request.get(`${origin}/v1/portal/fiscal-intents?unit_id=unit-a`)).json()).rows;
  const row=receipts.find(r=>r.intent_id===intent);
  expect(row.state).toBe("recorded"); expect(row.fiscal_confirmation).toBe("not_inferred_from_receipt");
  const entries=(await (await page.request.get(`${origin}/v1/portal/surfaces/inutilizations?unit_id=unit-a`)).json()).rows;
  expect(entries.filter(e=>e.entry_id===row.reference_id)).toHaveLength(1);
  expect(JSON.stringify(receipts)).not.toContain("original_key");
  expect(JSON.stringify(receipts)).not.toContain("Justificativa sintetica");
  const storage=await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}));
  expect(storage).toEqual({local:0,session:0});
  fs.mkdirSync(".artifacts/p02-t07",{recursive:true});
  for(const width of [320,390,1280]) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(()=>window.scrollTo(0,0));
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:`.artifacts/p02-t07/recovery-${width}.png`,fullPage:true});
  }
});

test("lost prepare response before dispatch recovers receipt without creating another",async({page})=>{
  await login(page); await fill(page,32);
  let intent;
  await page.route("**/fiscal-intents/prepare/inutilizeFiscalRange",async route=>{
    // Forward to real HTTP/SQLite and lose only the response after preparation.
    const response=await route.fetch(); expect(response.status()).toBe(200);
    intent=(await response.json()).intent_id;
    await route.abort("failed");
  });
  await page.getByRole("button",{name:"Solicitar inutilização",exact:true}).click();
  await expect(page.locator("#inutilization-result")).not.toHaveText("");
  await page.unroute("**/fiscal-intents/prepare/inutilizeFiscalRange");
  expect(intent).toBeTruthy();
  const before=(await (await page.request.get(`${origin}/v1/portal/fiscal-intents?unit_id=unit-a`)).json()).rows.find(r=>r.intent_id===intent);
  expect(before.state).toBe("prepared");
  await page.reload(); await fill(page,32); await resumeButton(page,intent).click();
  await page.getByRole("button",{name:"Solicitar inutilização",exact:true}).click();
  await expect(page.locator("#inutilization-result")).toContainText("Synthetic response loss");
  await page.getByRole("button",{name:"Solicitar inutilização",exact:true}).click();
  await expect(page.locator("#inutilization-result")).toContainText("Resposta recebida do executor");
  const after=(await (await page.request.get(`${origin}/v1/portal/fiscal-intents?unit_id=unit-a`)).json()).rows;
  expect(after.filter(r=>r.intent_id===intent)).toHaveLength(1);
  expect(after.find(r=>r.intent_id===intent).state).toBe("recorded");
});
