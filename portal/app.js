"use strict";

const navigation = [
  {
    label: "Operação",
    items: [
      ["overview", "Visão geral"],
      ["documents", "Documentos"],
      ["issuances", "Emissões"],
      ["errors", "Erros"],
      ["reconciliation", "Reconciliação"],
    ],
  },
  {
    label: "Configuração",
    items: [
      ["onboarding", "Onboarding"],
      ["companies", "Empresas"],
      ["units", "Unidades"],
      ["environments", "Ambientes"],
      ["capabilities", "Capabilities"],
      ["certificates", "Certificados"],
      ["providers", "Providers"],
    ],
  },
  {
    label: "Plataforma",
    items: [
      ["webhooks", "Webhooks"],
      ["integrations", "Integrações"],
      ["usage", "Uso"],
      ["billing", "Billing"],
      ["plans", "Planos"],
      ["audit", "Auditoria"],
      ["support", "Suporte"],
      ["settings", "Configurações"],
    ],
  },
];

const views = navigation.flatMap((group) => group.items);

const syntheticRows = {
  onboarding: [
    ["Organização demonstrativa", "12/14 etapas", "EM_PROGRESSO"],
    ["Tenant Sandbox", "14/14 etapas", "READY_INTERNAL"],
  ],
  companies: [["Empresa demonstrativa", "Cadastro sintético", "ATIVA"]],
  units: [["Unidade São Paulo", "HOMOLOGAÇÃO", "CONFIGURADA"]],
  environments: [
    ["Homologação", "Habilitado", "READY_INTERNAL"],
    ["Produção", "Evidence + approval", "BLOCKED_EXTERNAL"],
  ],
  capabilities: [
    ["NF-e", "SP / homologação", "READY_INTERNAL"],
    ["NFC-e", "SP / homologação", "BLOCKED_EXTERNAL"],
    ["NFS-e", "Município demonstrativo", "BLOCKED_EXTERNAL"],
  ],
  documents: [
    ["DOC-SYN-00041", "NF-e", "AUTHORIZED_SYNTHETIC"],
    ["DOC-SYN-00042", "NFC-e", "PENDING_SYNTHETIC"],
  ],
  issuances: [["ISS-SYN-00018", "Idempotency preservada", "CONCLUÍDA"]],
  errors: [["Sem erros críticos internos", "Último gate", "VERDE"]],
  reconciliation: [["REC-SYN-00007", "Provider state", "RECONCILIADO"]],
  webhooks: [["Destino sandbox", "HTTPS + assinatura", "CONFIGURADO"]],
  integrations: [
    ["ERP demonstrativo", "Bridge API V1", "READY_INTERNAL"],
    ["SaaS demonstrativo", "Webhook assinado", "READY_INTERNAL"],
    ["Ambiente de testes", "Sandbox", "CONFIGURADO"],
  ],
  certificates: [["cert-ref-demo", "Referência opaca", "SEM_SEGREDO_EM_TELA"]],
  providers: [["provider-demo", "Binding por capability", "HOMOLOGAÇÃO"]],
  usage: [["documents.issue", "312 / quota sintética", "DENTRO_DO_LIMITE"]],
  billing: [["Conta demonstrativa", "Trial interno", "AUTORIDADE_SEPARADA"]],
  plans: [
    ["Foundation", "Configurável", "SEM_PREÇO_HARDCODED"],
    ["Growth", "Configurável", "SEM_PREÇO_HARDCODED"],
    ["Enterprise", "Configurável", "SEM_PREÇO_HARDCODED"],
  ],
  audit: [["AUD-SYN-0091", "Configuração", "PROVENIÊNCIA_PRESERVADA"]],
  support: [["Catálogo operacional", "SEV1–SEV4", "RUNBOOKS"]],
  settings: [["Governança", "Fail-closed", "ATIVA"]],
};

const descriptions = {
  overview: "Visão governada da operação fiscal, do onboarding ao lifecycle do documento.",
  onboarding: "Entrada de clientes por configuração versionada, sem mudança de código para capacidades já suportadas.",
  companies: "Empresas isoladas no Control Plane com autoridade e escopo explícitos.",
  units: "Unidades fiscais separadas por tenant, unidade, jurisdição e ambiente.",
  environments: "Homologação e produção permanecem segregadas e não compartilham autoridade implícita.",
  capabilities: "Readiness é consultado e provado por evidência; nunca inferido por presença de configuração.",
  documents: "Lifecycle documental com referência, correlação, archive e trilha auditável.",
  issuances: "Operações idempotentes, rastreáveis e protegidas contra replay indevido.",
  errors: "Falhas operacionais apresentadas com contexto suficiente, sem exposição de segredo.",
  reconciliation: "Convergência segura entre estado interno e provider, sem blind retry.",
  webhooks: "Entrega assinada, retry governado e proteção contra replay.",
  integrations: "Bridge/API desacoplada para integrar SaaS, ERPs e plataformas digitais.",
  certificates: "A interface manipula referências; material criptográfico real permanece no secret backend.",
  providers: "Bindings por documento, operação, jurisdição e ambiente.",
  usage: "Medição comercial independente da autoridade fiscal já constituída.",
  billing: "Billing, plano e cobrança não concedem autorização fiscal automaticamente.",
  plans: "Planos e entitlements configuráveis, sem regras fiscais duplicadas.",
  audit: "Eventos administrativos e operacionais com provenance e correlation.",
  support: "Severidades, health states e runbooks preparados para operação assistida.",
  settings: "Políticas de segurança, isolamento, retenção e human gates.",
};

const nav = document.getElementById("nav");
const workspace = document.getElementById("workspace");
const title = document.getElementById("view-title");
const dialog = document.getElementById("confirm-dialog");
const newAction = document.getElementById("new-action");
const environmentButton = document.getElementById("environment-button");
const docsAction = document.getElementById("docs-action");

if (!nav || !workspace || !title || !(dialog instanceof HTMLDialogElement)) {
  throw new Error("FM NFCORE V1.0 portal shell is incomplete");
}

function escapeText(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function badgeTone(state) {
  const value = state.toUpperCase();
  if (/BLOCKED|PENDING|PROGRESSO|HOMOLOGAÇÃO/.test(value)) return "warning";
  if (/ERRO|ERROR|FAIL|REJECT/.test(value)) return "danger";
  if (/READY|VERDE|ATIVA|AUTHORIZED|CONCLUÍDA|RECONCILIADO|DENTRO|CONFIGURADO/.test(value)) return "success";
  return "neutral";
}

function rowMarkup(row) {
  const [name, context, state] = row.map(escapeText);
  return `<div class="row"><strong>${name}</strong><span class="state">${context}</span><span class="badge ${badgeTone(state)}">${state}</span></div>`;
}

function overviewMarkup() {
  return `
    <article class="panel">
      <div class="panel-header">
        <div><p class="eyebrow">Control Plane</p><h2>Prontidão interna V1</h2></div>
        <span class="badge success">CERTIFIED_INTERNAL</span>
      </div>
      <p>O núcleo V1 está estruturado para emissão governada, onboarding configurável e operação com rastreabilidade. Gates externos continuam explícitos antes da ativação produtiva.</p>
      <div class="progress" aria-label="Prontidão técnica interna da V1: certificada"><span></span></div>
    </article>

    <article class="panel">
      <div class="panel-header">
        <div><p class="eyebrow">External gates</p><h2>Antes do go-live</h2></div>
        <span class="badge warning">PROD BLOQUEADA</span>
      </div>
      <div class="status-list">
        <div class="status-item"><span>Certificados e credenciais reais</span><strong>BLOCKED_EXTERNAL</strong></div>
        <div class="status-item"><span>Homologação oficial aplicável</span><strong>EVIDENCE_REQUIRED</strong></div>
        <div class="status-item"><span>Piloto e ativação produtiva</span><strong>HUMAN_APPROVAL_REQUIRED</strong></div>
      </div>
    </article>

    <article class="panel full">
      <div class="panel-header">
        <div><p class="eyebrow">V1 Product pillars</p><h2>Infraestrutura fiscal governada</h2></div>
        <span class="badge">FM NFCORE V1.0</span>
      </div>
      <div class="pillar-grid">
        <div class="pillar"><span>01 · EMIT</span><strong>Emissão fiscal</strong><p>NF-e, NFC-e e NFS-e por contratos versionados.</p></div>
        <div class="pillar"><span>02 · CONTROL</span><strong>Governança</strong><p>Tenant, unidade, ambiente, capability e readiness explícitos.</p></div>
        <div class="pillar"><span>03 · TRACE</span><strong>Rastreabilidade</strong><p>Idempotência, correlation, audit, archive e reconciliation.</p></div>
        <div class="pillar"><span>04 · SCALE</span><strong>Integração</strong><p>Bridge/API, webhooks e onboarding zero-code para clientes suportados.</p></div>
      </div>
    </article>

    <article class="panel full">
      <div class="panel-header">
        <div><p class="eyebrow">Document coverage</p><h2>Escopo comercial da V1</h2></div>
        <span class="badge success">3 DOCUMENTOS</span>
      </div>
      <div class="grid-list">
        ${rowMarkup(["NF-e", "Mercadorias / operações aplicáveis", "V1_CORE"])}
        ${rowMarkup(["NFC-e", "Varejo / consumidor final", "V1_CORE"])}
        ${rowMarkup(["NFS-e", "Serviços / cobertura homologada", "V1_CORE"])}
      </div>
    </article>`;
}

function genericMarkup(viewId) {
  const rows = syntheticRows[viewId] || [];
  const rowsHtml = rows.length
    ? rows.map(rowMarkup).join("")
    : '<div class="empty-state">Nenhum registro sintético nesta superfície.</div>';
  return `
    <article class="panel full">
      <div class="panel-header">
        <div><p class="eyebrow">FM NFCORE V1.0</p><h2>${escapeText(descriptions[viewId] || "Superfície governada")}</h2></div>
        <span class="badge neutral">DADOS SINTÉTICOS</span>
      </div>
      <div class="grid-list">${rowsHtml}</div>
    </article>
    <article class="panel">
      <p class="eyebrow">Security model</p><h2>Fail-closed</h2>
      <p>Ausência de capability, entitlement, binding, evidence ou approval permanece bloqueio; a interface não converte configuração em autorização.</p>
    </article>
    <article class="panel">
      <p class="eyebrow">Secret handling</p><h2>Sem segredo em tela</h2>
      <p>Reference-only: certificados, CSC, tokens e credenciais são representados por referências opacas. Segredos reais não pertencem ao código nem à interface.</p>
    </article>`;
}

function render(viewId) {
  const view = views.find(([id]) => id === viewId) || views[0];
  const [resolvedId, label] = view;
  title.textContent = label;
  workspace.innerHTML = resolvedId === "overview" ? overviewMarkup() : genericMarkup(resolvedId);
  document.querySelectorAll(".nav-button").forEach((button) => {
    if (button.dataset.view === resolvedId) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}

for (const group of navigation) {
  const section = document.createElement("section");
  section.className = "nav-group";

  const label = document.createElement("span");
  label.className = "nav-group-label";
  label.textContent = group.label;
  section.append(label);

  for (const [id, itemLabel] of group.items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nav-button";
    button.dataset.view = id;
    button.textContent = itemLabel;
    button.addEventListener("click", () => render(id));
    section.append(button);
  }

  nav.append(section);
}

newAction?.addEventListener("click", () => dialog.showModal());
environmentButton?.addEventListener("click", () => dialog.showModal());
docsAction?.addEventListener("click", () => render("support"));

dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close("cancel");
});

render("overview");
