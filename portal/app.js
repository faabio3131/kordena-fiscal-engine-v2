"use strict";

/** @typedef {{tenant_id:string, role:string, unit_ids:string[]|null, permissions:string[], supported_documents:string[], projection:Record<string, unknown>}} BootstrapState */
/** @typedef {{method?:string, headers?:Record<string,string>, body?:string}} ApiOptions */

const navigation = [
  { label: "Operação", items: [["overview", "Visão geral"], ["documents", "Documentos"], ["issuances", "Emissões"], ["errors", "Erros"], ["reconciliation", "Reconciliação"]] },
  { label: "Configuração", items: [["onboarding", "Onboarding"], ["companies", "Empresas"], ["units", "Unidades"], ["environments", "Ambientes"], ["capabilities", "Capabilities"], ["certificates", "Certificados"], ["providers", "Providers"], ["users", "Usuários"]] },
  { label: "Plataforma", items: [["webhooks", "Webhooks"], ["integrations", "Integrações"], ["usage", "Uso"], ["billing", "Billing"], ["plans", "Planos"], ["audit", "Auditoria"], ["support", "Suporte"], ["settings", "Configurações"]] },
];

const supportedDocumentLabels = ["NF-e", "NFC-e", "NFS-e"];
const safetyStates = {
  blocked: "PROD BLOQUEADA",
  external: "BLOCKED_EXTERNAL",
  approval: "HUMAN_APPROVAL_REQUIRED",
};

/** @type {Record<string,string>} */
const descriptions = {
  overview: "Visão governada da operação fiscal e do readiness real do tenant.",
  documents: "Lifecycle documental, consulta, archive e correlação.",
  issuances: "Emissões idempotentes e rastreáveis.",
  errors: "Falhas operacionais sem exposição de segredo.",
  reconciliation: "Convergência segura entre estado interno e provider.",
  onboarding: "Onboarding configurável por tenant e unidade.",
  companies: "Empresas visíveis no escopo autorizado da sessão.",
  units: "Unidades permitidas para o usuário autenticado.",
  environments: "Homologação e produção com autoridade segregada.",
  capabilities: "Capabilities e readiness baseados em evidência.",
  certificates: "Referências de certificado; material secreto nunca é exibido.",
  providers: "Bindings de providers por documento, operação e jurisdição.",
  users: "Usuários, papéis e permissões do tenant.",
  webhooks: "Destinos e estado de entrega governada.",
  integrations: "Integrações do tenant via contratos versionados.",
  usage: "Uso medido sem interferir na autoridade fiscal.",
  billing: "Cobrança separada da autoridade fiscal.",
  plans: "Plano e entitlements comerciais configurados.",
  audit: "Auditoria administrativa e operacional.",
  support: "Saúde operacional, incidentes e suporte.",
  settings: "Políticas e configurações autorizadas.",
};

const loginView = /** @type {HTMLElement} */ (document.getElementById("login-view"));
const appShell = /** @type {HTMLElement} */ (document.getElementById("app-shell"));
const loginForm = /** @type {HTMLFormElement} */ (document.getElementById("login-form"));
const loginEmail = /** @type {HTMLInputElement} */ (document.getElementById("login-email"));
const loginPassword = /** @type {HTMLInputElement} */ (document.getElementById("login-password"));
const loginError = /** @type {HTMLElement} */ (document.getElementById("login-error"));
const nav = /** @type {HTMLElement} */ (document.getElementById("nav"));
const workspace = /** @type {HTMLElement} */ (document.getElementById("workspace"));
const title = /** @type {HTMLElement} */ (document.getElementById("view-title"));
const authorityContext = /** @type {HTMLElement} */ (document.getElementById("authority-context"));
const runtimeState = /** @type {HTMLElement} */ (document.getElementById("runtime-state"));
const criticalTitle = /** @type {HTMLElement} */ (document.getElementById("critical-state-title"));
const criticalCopy = /** @type {HTMLElement} */ (document.getElementById("critical-state-copy"));
const logoutAction = /** @type {HTMLButtonElement} */ (document.getElementById("logout-action"));
const operationDialog = /** @type {HTMLDialogElement} */ (document.getElementById("operation-dialog"));
const operationForm = /** @type {HTMLFormElement} */ (document.getElementById("operation-form"));
const operationId = /** @type {HTMLSelectElement} */ (document.getElementById("operation-id"));
const operationUnit = /** @type {HTMLInputElement} */ (document.getElementById("operation-unit"));
const operationPayload = /** @type {HTMLTextAreaElement} */ (document.getElementById("operation-payload"));
const operationError = /** @type {HTMLElement} */ (document.getElementById("operation-error"));
const operationCancel = /** @type {HTMLButtonElement} */ (document.getElementById("operation-cancel"));

if (!loginView || !appShell || !loginForm || !nav || !workspace || !title || !operationDialog) {
  throw new Error("FM NFCORE portal shell is incomplete");
}

/** @type {BootstrapState|null} */
let bootstrapState = null;
let currentView = "overview";

function csrfToken() {
  const prefix = "nfcore_csrf=";
  const entry = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : "";
}

/** @param {string} path @param {ApiOptions} [options] @returns {Promise<any>} */
async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body && typeof body === "object" ? body.detail : null;
    const message = detail && typeof detail === "object" && typeof detail.message === "string"
      ? detail.message
      : `Falha HTTP ${response.status}`;
    throw Object.assign(new Error(message), { status: response.status, body });
  }
  return body;
}

/** @param {string} [message] */
function showLogin(message = "") {
  loginView.hidden = false;
  appShell.hidden = true;
  loginError.textContent = message;
}

function showApp() {
  loginView.hidden = true;
  appShell.hidden = false;
}

/** @param {unknown} value */
function text(value) {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** @param {unknown} value */
function tone(value) {
  const normalized = text(value).toUpperCase();
  if (/FAIL|ERROR|REJECT|UNAVAILABLE/.test(normalized)) return "danger";
  if (/BLOCKED|PENDING|MISSING|REQUIRED|HOMOLOG/.test(normalized)) return "warning";
  if (/READY|ACTIVE|ATIVA|AUTHORIZED|OK|HEALTHY|CONCLU/.test(normalized)) return "success";
  return "neutral";
}

/** @param {Record<string, unknown>} row */
function rowElement(row) {
  const wrapper = document.createElement("div");
  wrapper.className = "row";
  const entries = Object.entries(row);
  const primary = entries[0] || ["registro", "—"];
  const secondary = entries[1] || ["contexto", ""];
  const state = entries.find(([key]) => /state|status|readiness|health/i.test(key)) || entries[2] || ["status", ""];

  const strong = document.createElement("strong");
  strong.textContent = text(primary[1]);
  const context = document.createElement("span");
  context.className = "state";
  context.textContent = text(secondary[1]);
  const badge = document.createElement("span");
  badge.className = `badge ${tone(state[1])}`;
  badge.textContent = text(state[1]);
  wrapper.append(strong, context, badge);
  return wrapper;
}

/** @param {string} titleText @param {string} [eyebrow] */
function panel(titleText, eyebrow = "FM NFCORE V1.0") {
  const article = document.createElement("article");
  article.className = "panel full";
  const header = document.createElement("div");
  header.className = "panel-header";
  const heading = document.createElement("div");
  const eye = document.createElement("p");
  eye.className = "eyebrow";
  eye.textContent = eyebrow;
  const h2 = document.createElement("h2");
  h2.textContent = titleText;
  heading.append(eye, h2);
  header.append(heading);
  article.append(header);
  return article;
}

function renderOverview() {
  workspace.replaceChildren();
  const projection = bootstrapState?.projection || {};
  const article = panel("Estado operacional", "Control Plane");
  const grid = document.createElement("div");
  grid.className = "grid-list";
  const visible = Object.entries(projection);
  if (!visible.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "A API não retornou projeções operacionais para este escopo.";
    grid.append(empty);
  } else {
    for (const [key, value] of visible) grid.append(rowElement({ item: key, value, status: value }));
  }
  article.append(grid);

  const identity = panel("Autoridade da sessão", "Security boundary");
  const identityGrid = document.createElement("div");
  identityGrid.className = "grid-list";
  identityGrid.append(
    rowElement({ item: bootstrapState?.tenant_id, value: bootstrapState?.role, status: "SESSION_AUTHORITY" }),
    rowElement({ item: "Unidades", value: bootstrapState?.unit_ids || "todas autorizadas", status: "SCOPED" }),
    rowElement({ item: "Documentos", value: supportedDocumentLabels, status: "V1" }),
  );
  identity.append(identityGrid);
  workspace.append(article, identity);
}

/** @param {string} viewId */
async function renderSurface(viewId) {
  currentView = viewId;
  const label = navigation.flatMap((group) => group.items).find(([id]) => id === viewId)?.[1] || viewId;
  title.textContent = label;
  document.querySelectorAll(".nav-button").forEach((element) => {
    const button = /** @type {HTMLElement} */ (element);
    if (button.dataset.view === viewId) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (viewId === "overview") {
    renderOverview();
    return;
  }
  workspace.replaceChildren();
  const article = panel(descriptions[viewId] || label);
  const loading = document.createElement("p");
  loading.textContent = "Carregando dados autorizados...";
  article.append(loading);
  workspace.append(article);
  try {
    const response = await api(`/v1/portal/surfaces/${encodeURIComponent(viewId)}`);
    const grid = document.createElement("div");
    grid.className = "grid-list";
    const rows = Array.isArray(response.rows) ? response.rows : [];
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Nenhum registro disponível neste escopo autorizado.";
      grid.append(empty);
    } else {
      for (const row of rows) grid.append(rowElement(row));
    }
    const existingHeader = article.firstElementChild;
    article.replaceChildren(...(existingHeader ? [existingHeader, grid] : [grid]));
    if (["documents", "issuances", "reconciliation"].includes(viewId)) {
      const action = document.createElement("button");
      action.className = "primary";
      action.type = "button";
      action.textContent = "Executar operação governada";
      action.addEventListener("click", () => operationDialog.showModal());
      article.append(action);
    }
  } catch (error) {
    loading.textContent = error instanceof Error ? error.message : "Falha ao carregar superfície";
    loading.className = "form-error";
  }
}

function buildNavigation() {
  nav.replaceChildren();
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
      button.addEventListener("click", () => void renderSurface(id));
      section.append(button);
    }
    nav.append(section);
  }
}

/** @param {BootstrapState} state */
function applyBootstrap(state) {
  bootstrapState = state;
  showApp();
  authorityContext.textContent = `${state.tenant_id} · ${state.role}`;
  runtimeState.textContent = "API autenticada conectada";
  const productionState = state.projection.production_state || state.projection.readiness || safetyStates.approval;
  criticalTitle.textContent = text(productionState);
  criticalCopy.textContent = /READY|APPROVED/i.test(text(productionState))
    ? "Readiness retornado pelo backend; operações continuam sujeitas a RBAC e gates fiscais."
    : `${safetyStates.blocked}: Produção permanece bloqueada até que o backend comprove os gates aplicáveis (${safetyStates.external} / ${safetyStates.approval}).`;
  buildNavigation();
  renderOverview();
}

async function bootstrap() {
  try {
    /** @type {BootstrapState} */
    const state = await api("/v1/portal/bootstrap");
    applyBootstrap(state);
  } catch (error) {
    const status = error instanceof Error && "status" in error ? error.status : null;
    if (status === 401) showLogin();
    else showLogin(error instanceof Error ? error.message : "Portal indisponível");
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const email = loginEmail.value;
  const password = loginPassword.value;
  try {
    await api("/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    loginPassword.value = "";
    await bootstrap();
  } catch (error) {
    showLogin(error instanceof Error ? error.message : "Falha ao autenticar");
  }
});

logoutAction.addEventListener("click", async () => {
  try {
    await api("/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken() } });
  } finally {
    bootstrapState = null;
    showLogin();
  }
});

operationCancel.addEventListener("click", () => operationDialog.close());
operationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  operationError.textContent = "";
  try {
    const selected = operationId.value;
    const unitId = operationUnit.value.trim();
    const parsed = JSON.parse(operationPayload.value);
    const payload = { ...parsed, unit_id: unitId };
    const mutation = selected !== "queryFiscalDocument";
    /** @type {Record<string,string>} */
    const headers = { "X-CSRF-Token": csrfToken() };
    if (mutation) headers["Idempotency-Key"] = crypto.randomUUID();
    await api(`/v1/portal/operations/${encodeURIComponent(selected)}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    operationDialog.close();
    await renderSurface(currentView);
  } catch (error) {
    operationError.textContent = error instanceof Error ? error.message : "Operação rejeitada";
  }
});

void bootstrap();