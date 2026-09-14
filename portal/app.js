"use strict";

const views = [
  ["overview", "Visão geral"],
  ["onboarding", "Onboarding"],
  ["companies", "Empresas"],
  ["units", "Unidades"],
  ["environments", "Ambientes"],
  ["capabilities", "Capabilities"],
  ["documents", "Documentos"],
  ["issuances", "Emissões"],
  ["errors", "Erros"],
  ["reconciliation", "Reconciliação"],
  ["webhooks", "Webhooks"],
  ["integrations", "Integrações"],
  ["certificates", "Certificados"],
  ["providers", "Providers"],
  ["usage", "Uso"],
  ["billing", "Billing"],
  ["plans", "Planos"],
  ["audit", "Auditoria"],
  ["support", "Suporte"],
  ["settings", "Configurações"],
];

const syntheticRows = {
  onboarding: [
    ["Organização Demo", "12/14 etapas", "Em progresso"],
    ["Tenant Sandbox", "14/14 etapas", "Internamente pronto"],
  ],
  companies: [["FM Demo Comércio Ltda.", "CNPJ sintético", "Ativa"]],
  units: [["Unidade São Paulo", "HOMOLOG", "Configurada"]],
  environments: [
    ["Homologação", "Habilitado", "Referência interna"],
    ["Produção", "Bloqueado", "Requer readiness + gate humano"],
  ],
  capabilities: [
    ["NF-e authorize", "SP / homolog", "READY_INTERNAL"],
    ["NFC-e authorize", "SP / homolog", "BLOCKED_EXTERNAL"],
    ["NFS-e authorize", "Município demo", "BLOCKED_EXTERNAL"],
  ],
  documents: [["DOC-SYN-00041", "NF-e", "Autorizado sintético"]],
  issuances: [["ISS-SYN-00018", "Idempotency preservada", "Concluída"]],
  errors: [["Sem erros críticos internos", "Último gate", "Verde"]],
  reconciliation: [["REC-SYN-00007", "Provider state", "Reconciliado"]],
  webhooks: [["Destino demo", "HTTPS / referência", "Assinatura exigida"]],
  integrations: [
    ["Kordena", "FISC-20", "BLOCKED_PRODUCT"],
    ["Iron Fit", "Charge paid", "READY_INTERNAL"],
    ["Vendedor IA", "Dados fiscais", "BLOCKED_PRODUCT"],
    ["CampaIA", "Own billing authority", "BLOCKED_PRODUCT"],
  ],
  certificates: [["cert-ref-demo", "Somente referência", "Sem material secreto"]],
  providers: [["provider-demo", "Binding por capability", "Homologação"]],
  usage: [["documents.issue", "312 / quota sintética", "Dentro do limite"]],
  billing: [["Conta demo", "Trial interno", "Fiscal authority separada"]],
  plans: [
    ["Foundation", "Configurável", "Sem preço hardcoded"],
    ["Growth", "Configurável", "Sem preço hardcoded"],
    ["Enterprise", "Configurável", "Sem preço hardcoded"],
  ],
  audit: [["AUD-SYN-0091", "Configuração", "Proveniência preservada"]],
  support: [["Catálogo operacional", "SEV1–SEV4", "Targets técnicos"]],
  settings: [["Governança", "Fail-closed", "Ativa"]],
};

const descriptions = {
  overview: "Estado técnico e comercial interno do FM Fiscal sem conceder autoridade produtiva.",
  onboarding: "Fluxo resumível, idempotente e reference-only para entrada de clientes.",
  companies: "Empresas configuradas no Control Plane sem acoplamento a produto consumidor.",
  units: "Unidades e escopos fiscais isolados por tenant, unidade e ambiente.",
  environments: "Separação explícita entre homologação e produção.",
  capabilities: "Readiness e capability são consultados; nunca inferidos pela interface.",
  documents: "Referências de documentos e lifecycle com trilha auditável.",
  issuances: "Operações sintéticas com idempotência e correlation preservadas.",
  errors: "Erros operacionais apresentados sem expor dados sensíveis.",
  reconciliation: "Convergência entre estado interno e provider sem blind retry.",
  webhooks: "Destinos HTTPS e verificação de assinatura/replay.",
  integrations: "Situação dos consumidores sem transformar blockers em verde artificial.",
  certificates: "A interface manipula referências; material criptográfico real fica fora dela.",
  providers: "Bindings governados por documento, jurisdição, operação e ambiente.",
  usage: "Medição comercial separada do estado fiscal já legitimamente constituído.",
  billing: "Billing comercial não é autoridade de documento fiscal.",
  plans: "Planos e entitlements configuráveis, sem preço final embutido.",
  audit: "Eventos administrativos e operacionais com provenance e correlation.",
  support: "Runbooks, severidades e health states técnicos para operação assistida.",
  settings: "Políticas que preservam fail-closed, isolamento e human gates.",
};

const nav = document.getElementById("nav");
const workspace = document.getElementById("workspace");
const title = document.getElementById("view-title");
const dialog = document.getElementById("confirm-dialog");
const newAction = document.getElementById("new-action");
const environmentButton = document.getElementById("environment-button");

if (!nav || !workspace || !title || !(dialog instanceof HTMLDialogElement)) {
  throw new Error("Premium portal shell is incomplete");
}

function escapeText(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function rowMarkup(row) {
  const [name, context, state] = row.map(escapeText);
  const warning = /BLOCKED|Bloqueado/.test(state) ? " warning" : "";
  return `<div class="row"><strong>${name}</strong><span class="state">${context}</span><span class="badge${warning}">${state}</span></div>`;
}

function overviewMarkup() {
  return `
    <article class="panel">
      <div class="panel-header"><div><p class="eyebrow">Convergência</p><h2>Prontidão interna</h2></div><span class="badge">READY_INTERNAL</span></div>
      <p>Rehearsal de cutover e rollback estão certificados internamente. Produção permanece protegida por gates externos e humanos.</p>
      <div class="progress" aria-label="Progresso interno de referência: 96%"><span></span></div>
    </article>
    <article class="panel">
      <div class="panel-header"><div><p class="eyebrow">Authority</p><h2>Barreiras ativas</h2></div><span class="badge warning">PROD BLOQUEADA</span></div>
      <div class="status-list">
        <div class="status-item"><span>Kordena / FISC-20</span><strong>BLOCKED_PRODUCT</strong></div>
        <div class="status-item"><span>Homologação oficial</span><strong>BLOCKED_EXTERNAL</strong></div>
        <div class="status-item"><span>Cutover real</span><strong>HUMAN_APPROVAL_REQUIRED</strong></div>
      </div>
    </article>
    <article class="panel full">
      <div class="panel-header"><div><p class="eyebrow">Produto</p><h2>Superfícies comerciais</h2></div><span class="badge">Referência premium</span></div>
      <div class="grid-list">
        ${rowMarkup(["Self-service onboarding", "Checkpoint + resume", "Certificado internamente"])}
        ${rowMarkup(["Plans & entitlements", "Configurável", "Certificado internamente"])}
        ${rowMarkup(["SDKs", "Python + TypeScript reference", "Certificado internamente"])}
        ${rowMarkup(["Compliance técnico", "LEGAL_VALIDATION_REQUIRED quando aplicável", "Certificado internamente"])}
      </div>
    </article>`;
}

function genericMarkup(viewId) {
  const rows = syntheticRows[viewId] || [];
  const rowsHtml = rows.length
    ? rows.map(rowMarkup).join("")
    : '<div class="empty-state">Nenhum registro sintético nesta referência.</div>';
  return `
    <article class="panel full">
      <div class="panel-header"><div><p class="eyebrow">FM Fiscal</p><h2>${escapeText(descriptions[viewId] || "Superfície governada")}</h2></div><span class="badge">DEMO INTERNA</span></div>
      <div class="grid-list">${rowsHtml}</div>
    </article>
    <article class="panel">
      <p class="eyebrow">Segurança</p><h2>Fail-closed</h2>
      <p>Ausência de capability, entitlement, binding, evidence ou approval não é convertida em permissão.</p>
    </article>
    <article class="panel">
      <p class="eyebrow">Privacidade</p><h2>Sem segredo em tela</h2>
      <p>Certificados, CSC, tokens e credenciais são representados apenas por referências fictícias.</p>
    </article>`;
}

function render(viewId) {
  const view = views.find(([id]) => id === viewId) || views[0];
  const [resolvedId, label] = view;
  title.textContent = label;
  workspace.innerHTML = resolvedId === "overview" ? overviewMarkup() : genericMarkup(resolvedId);
  document.querySelectorAll(".nav-button").forEach((button) => {
    if (button.dataset.view === resolvedId) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });
}

for (const [id, label] of views) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-button";
  button.dataset.view = id;
  button.textContent = label;
  button.addEventListener("click", () => render(id));
  nav.append(button);
}

newAction?.addEventListener("click", () => dialog.showModal());
environmentButton?.addEventListener("click", () => dialog.showModal());

dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close("cancel");
});

render("overview");
