"use strict";

/** @typedef {{tenant_id:string, role:string, unit_ids:string[]|null, platform_admin:boolean, permissions:string[], supported_documents:string[], projection:Record<string, unknown>}} BootstrapState */
/** @typedef {{method?:string, headers?:Record<string,string>, body?:string}} ApiOptions */

const navigation = [
  { label: "Operação", items: [["overview", "Visão geral"], ["documents", "Documentos"], ["issuances", "Emissões"], ["errors", "Erros"], ["reconciliation", "Reconciliação"]] },
  { label: "Configuração", items: [["onboarding", "Onboarding"], ["companies", "Empresas"], ["units", "Unidades"], ["environments", "Ambientes"], ["capabilities", "Capabilities"], ["certificates", "Certificados"], ["providers", "Providers"], ["users", "Usuários"]] },
  { label: "Plataforma", items: [["webhooks", "Webhooks"], ["webhook-egress", "Aprovação de egress"], ["integrations", "Integrações"], ["usage", "Uso"], ["billing", "Billing"], ["plans", "Planos"], ["pricing-admin", "Catálogo comercial"], ["commercial-release", "Liberação comercial"], ["checkout-admin", "Canais de Venda / Checkout"], ["audit", "Auditoria"], ["support", "Suporte"], ["settings", "Configurações"]] },
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
  "webhook-egress": "Aprovação e revogação de destinos pela autoridade da plataforma.",
  integrations: "Integrações do tenant via contratos versionados.",
  usage: "Uso medido sem interferir na autoridade fiscal.",
  billing: "Cobrança separada da autoridade fiscal.",
  plans: "Plano e entitlements comerciais configurados.",
  "pricing-admin": "Catálogo comercial versionado, durável e restrito à administração da plataforma.",
  "commercial-release": "Decisão humana versionada que governa a disponibilidade comercial pública do NFCore.",
  "checkout-admin": "Canais de venda governados por adapters. O provider configurado traduz checkout e eventos sem virar autoridade comercial do NFCore.",
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
const forgotPasswordAction = /** @type {HTMLButtonElement} */ (document.getElementById("forgot-password-action"));
const passwordResetRequestForm = /** @type {HTMLFormElement} */ (document.getElementById("password-reset-request-form"));
const passwordResetEmail = /** @type {HTMLInputElement} */ (document.getElementById("password-reset-email"));
const passwordResetRequestCancel = /** @type {HTMLButtonElement} */ (document.getElementById("password-reset-request-cancel"));
const passwordResetRequestStatus = /** @type {HTMLElement} */ (document.getElementById("password-reset-request-status"));
const passwordResetCompleteForm = /** @type {HTMLFormElement} */ (document.getElementById("password-reset-complete-form"));
const passwordResetNewPassword = /** @type {HTMLInputElement} */ (document.getElementById("password-reset-new-password"));
const passwordResetCompleteStatus = /** @type {HTMLElement} */ (document.getElementById("password-reset-complete-status"));
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
const fiscalViews = new Set(["documents", "issuances", "errors", "reconciliation", "capabilities"]);
const configurationViews = new Set(["certificates", "providers", "webhooks", "integrations", "settings"]);
const scopedViews = new Set([...fiscalViews, ...configurationViews]);
let selectedFiscalUnit = "";
let selectedFiscalEnvironment = "homologation";
let fiscalPageOffset = 0;
/** @type {{fingerprint:string, key:string}|null} */
let pendingFiscalRequest = null;
const fiscalOperationPermissions = {
  issueFiscalDocument: "document.issue",
  queryFiscalDocument: "document.query",
  cancelFiscalDocument: "document.cancel",
  inutilizeFiscalRange: "document.inutilize",
  reconcileFiscalOperation: "reconciliation.execute",
};

/** @returns {{unit_id:string, display_name:string, environments:string[]}[]} */
function authorizedFiscalUnits() {
  const units = bootstrapState?.projection.authorized_units;
  if (!Array.isArray(units)) return [];
  return units.filter((unit) => unit && typeof unit.unit_id === "string"
    && typeof unit.display_name === "string" && Array.isArray(unit.environments));
}

/** @param {HTMLElement} article @param {string} viewId */
function appendFiscalFilters(article, viewId) {
  const units = authorizedFiscalUnits();
  if (!units.some((unit) => unit.unit_id === selectedFiscalUnit)) selectedFiscalUnit = units[0]?.unit_id || "";
  const unitLabel = document.createElement("label");
  unitLabel.textContent = "Unidade fiscal";
  const select = document.createElement("select");
  select.id = "fiscal-unit-filter";
  for (const unit of units) {
    const option = document.createElement("option");
    option.value = unit.unit_id; option.textContent = unit.display_name;
    select.append(option);
  }
  select.value = selectedFiscalUnit;
  select.addEventListener("change", () => {
    selectedFiscalUnit = select.value; fiscalPageOffset = 0; void renderSurface(viewId);
  });
  unitLabel.append(select); article.append(unitLabel);
  const environments = units.find((unit) => unit.unit_id === selectedFiscalUnit)?.environments || [];
  if (!environments.includes(selectedFiscalEnvironment)) selectedFiscalEnvironment = environments[0] || "homologation";
  const envLabel = document.createElement("label");
  envLabel.textContent = "Ambiente fiscal";
  const envSelect = document.createElement("select");
  envSelect.id = "fiscal-environment-filter";
  for (const environment of environments) {
    const option = document.createElement("option");
    option.value = environment;
    option.textContent = environment === "production" ? configurationViews.has(viewId) ? "Produção — configuração não autoriza operação" : "Produção — consulta de estado" : "Homologação";
    envSelect.append(option);
  }
  envSelect.value = selectedFiscalEnvironment;
  envSelect.addEventListener("change", () => {
    selectedFiscalEnvironment = envSelect.value; fiscalPageOffset = 0; void renderSurface(viewId);
  });
  envLabel.append(envSelect); article.append(envLabel);
  const notice = document.createElement("p");
  notice.textContent = configurationViews.has(viewId)
    ? "Configuração persistida por unidade e ambiente. Até 100 registros por tipo nesta página. Bindings de integração seguem o escopo do modelo existente."
    : "Estado registrado no backend. Readiness declarado não autoriza operação. Registros legados sem escopo comprovado não são exibidos. Até 100 registros por tipo nesta página.";
  article.append(notice);
}

/** @param {HTMLElement} article */
function appendFiscalActions(article) {
  const operations = bootstrapState?.projection.configured_fiscal_operations;
  const configured = Array.isArray(operations) ? operations : [];
  for (const option of operationId.options) {
    const permission = fiscalOperationPermissions[/** @type {keyof typeof fiscalOperationPermissions} */ (option.value)];
    option.disabled = !configured.includes(option.value) || !bootstrapState?.permissions.includes(permission);
    option.hidden = option.disabled;
  }
  const allowed = Array.from(operationId.options).filter((option) => !option.disabled);
  if (!allowed.length) {
    const blocked = document.createElement("p");
    blocked.setAttribute("role", "status");
    blocked.textContent = "Operação fiscal indisponível neste escopo: executor não configurado ou permissão ausente. Nenhuma emissão foi realizada.";
    article.append(blocked);
    return;
  }
  operationId.value = allowed[0].value;
  const action = document.createElement("button");
  action.className = "primary"; action.type = "button";
  action.textContent = "Executar operação governada";
  action.addEventListener("click", () => {
    operationUnit.value = selectedFiscalUnit;
    operationDialog.showModal();
  });
  article.append(action);
}


function csrfToken() {
  const prefix = "nfcore_csrf=";
  const entry = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : "";
}

/** @returns {string|null} */
function resetTokenFromLocation() {
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const fragmentToken = fragment.get("token");
  if (fragmentToken) return fragmentToken;
  // Temporary compatibility for previously issued links. New activation delivery uses
  // the fragment so raw reset tokens are not sent in the initial HTTP request.
  return new URLSearchParams(window.location.search).get("reset_token");
}

function clearResetTokenFromLocation() {
  const url = new URL(window.location.href);
  url.searchParams.delete("reset_token");
  const fragment = new URLSearchParams(url.hash.replace(/^#/, ""));
  fragment.delete("token");
  const remainingFragment = fragment.toString();
  url.hash = remainingFragment ? `#${remainingFragment}` : "";
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

/** @type {string|null} */
let pendingPasswordResetToken = resetTokenFromLocation();
if (pendingPasswordResetToken) clearResetTokenFromLocation();

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

function showPasswordResetRequest() {
  loginForm.hidden = true;
  passwordResetCompleteForm.hidden = true;
  passwordResetRequestForm.hidden = false;
  passwordResetEmail.value = loginEmail.value;
  passwordResetRequestStatus.textContent = "";
}

function showRegularLogin() {
  passwordResetRequestForm.hidden = true;
  passwordResetCompleteForm.hidden = true;
  loginForm.hidden = false;
}

function showPasswordResetCompletion() {
  loginView.hidden = false;
  appShell.hidden = true;
  loginForm.hidden = true;
  passwordResetRequestForm.hidden = true;
  passwordResetCompleteForm.hidden = false;
  passwordResetCompleteStatus.textContent = "";
}

/** @param {unknown} error */
function passwordResetErrorCode(error) {
  const body = error && typeof error === "object" && "body" in error
    ? error.body
    : null;
  const detail = body && typeof body === "object" && "detail" in body
    ? body.detail
    : null;
  return detail && typeof detail === "object" && "code" in detail
    && typeof detail.code === "string"
    ? detail.code
    : "";
}

/** @param {unknown} error */
function passwordResetErrorMessage(error) {
  const code = passwordResetErrorCode(error);
  if (code === "PASSWORD_POLICY_INVALID") {
    return "A senha deve ter entre 12 e 1024 caracteres. Letras, números, espaços e símbolos são permitidos.";
  }
  if (code === "PASSWORD_RESET_NOT_USABLE") {
    return "Este link de recuperação não é mais válido. Solicite um novo link e use somente o e-mail mais recente.";
  }
  return error instanceof Error ? error.message : "Não foi possível alterar a senha.";
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

/** @param {Record<string, unknown>} row */
function fiscalRowElement(row) {
  const primary = row.document_id || row.document_reference || row.source_id || row.entry_id || row.reference_id || row.binding_id || row.destination_id || row.module_id || row.policy_id || row.document_kind || "Registro";
  const state = row.readiness || row.state || row.status || row.kind || "registrado";
  const display = {registro: primary, escopo: `${text(row.unit_id)} · ${text(row.environment)} · ${text(row.record_type || row.code || "capability")}`, state};
  const wrapper = rowElement(display);
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Detalhes do registro";
  const values = document.createElement("dl");
  for (const [key, value] of Object.entries(row)) {
    const term = document.createElement("dt"); term.textContent = key;
    const description = document.createElement("dd"); description.textContent = text(value);
    values.append(term, description);
  }
  details.append(summary, values); wrapper.append(details);
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
  const visible = Object.entries(projection).filter(([key]) => key !== "available_surfaces");
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

/** @param {HTMLElement} article */
function appendOnboardingControls(article) {
  const stage = bootstrapState?.projection.onboarding_stage;
  if (stage === "commercial_provisioning_required") {
    const notice = document.createElement("div");
    notice.className = "empty-state";
    notice.textContent = "O provisioning comercial confiável da organização precisa ser concluído antes da configuração da unidade.";
    article.append(notice);
    return;
  }
  if (stage !== "unit_setup_required" || !bootstrapState?.permissions.includes("configuration.write")) return;

  const form = document.createElement("form");
  form.className = "panel-form";
  const unitLabel = document.createElement("label");
  unitLabel.textContent = "Código da unidade";
  const unitInput = document.createElement("input");
  unitInput.name = "unit_id";
  unitInput.required = true;
  unitInput.autocomplete = "off";
  const nameLabel = document.createElement("label");
  nameLabel.textContent = "Nome da unidade";
  const nameInput = document.createElement("input");
  nameInput.name = "display_name";
  nameInput.required = true;
  nameInput.autocomplete = "organization";
  unitLabel.append(unitInput);
  nameLabel.append(nameInput);
  const submit = document.createElement("button");
  submit.className = "primary";
  submit.type = "submit";
  submit.textContent = "Cadastrar unidade em homologação";
  const statusLine = document.createElement("p");
  statusLine.className = "form-error";
  statusLine.setAttribute("role", "status");
  form.append(unitLabel, nameLabel, submit, statusLine);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusLine.textContent = "";
    submit.disabled = true;
    try {
      await api("/v1/portal/operations/onboardUnit", {
        method: "POST",
        headers: {
          "X-CSRF-Token": csrfToken(),
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          unit_id: unitInput.value.trim(),
          display_name: nameInput.value.trim(),
        }),
      });
      await bootstrap();
      await renderSurface("onboarding");
    } catch (error) {
      statusLine.textContent = error instanceof Error ? error.message : "Não foi possível cadastrar a unidade";
    } finally {
      submit.disabled = false;
    }
  });
  article.append(form);
}

async function renderPricingAdmin() {
  workspace.replaceChildren();
  const article = panel("Catálogo comercial", "Platform administration");
  const statusLine = document.createElement("p");
  statusLine.className = "form-error";
  statusLine.setAttribute("role", "status");
  article.append(statusLine);
  workspace.append(article);

  if (!bootstrapState?.platform_admin) {
    statusLine.textContent = "A administração do catálogo exige autoridade explícita de plataforma.";
    return;
  }

  try {
    const response = await api("/v1/admin/pricing");
    const current = response.current && typeof response.current === "object" ? response.current : null;
    const history = Array.isArray(response.history) ? response.history : [];

    const summary = document.createElement("div");
    summary.className = "grid-list";
    summary.append(
      rowElement({
        item: "Estado",
        value: current ? "Catálogo publicado" : "Sem preço comercial publicado",
        status: current ? "PUBLISHED" : "UNPRICED",
      }),
      rowElement({
        item: "Versão ativa",
        value: current && typeof current.version === "number" ? current.version : "—",
        status: "VERSIONED",
      }),
      rowElement({
        item: "Histórico",
        value: history.length,
        status: "AUDITED",
      }),
    );

    const form = document.createElement("form");
    form.className = "panel-form";
    const label = document.createElement("label");
    label.textContent = "Próxima configuração JSON";
    const editor = document.createElement("textarea");
    editor.rows = 18;
    editor.spellcheck = false;
    const draft = current
      ? { ...current, version: Number(current.version) + 1 }
      : { configuration_id: "nfcore-commercial", version: 1, prices: [], plans: [] };
    editor.value = JSON.stringify(draft, null, 2);
    label.append(editor);

    const publish = document.createElement("button");
    publish.className = "primary";
    publish.type = "submit";
    publish.textContent = "Publicar nova versão";
    const warning = document.createElement("p");
    warning.className = "empty-state";
    warning.textContent = "Preços são configuração operacional. Nenhum valor deve ser inventado ou copiado para o código-fonte.";

    form.append(label, warning, publish);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      publish.disabled = true;
      statusLine.textContent = "";
      try {
        const configuration = JSON.parse(editor.value);
        const expectedVersion = current && typeof current.version === "number" ? current.version : null;
        await api("/v1/admin/pricing", {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken() },
          body: JSON.stringify({
            configuration,
            expected_version: expectedVersion,
          }),
        });
        await renderPricingAdmin();
      } catch (error) {
        statusLine.textContent = error instanceof Error ? error.message : "Não foi possível publicar o catálogo";
      } finally {
        publish.disabled = false;
      }
    });

    article.replaceChildren(summary, form, statusLine);
  } catch (error) {
    statusLine.textContent = error instanceof Error ? error.message : "Falha ao carregar catálogo comercial";
  }
}

async function renderCommercialRelease() {
  workspace.replaceChildren();
  const article = panel("Liberação comercial", "Platform administration");
  const statusLine = document.createElement("p");
  statusLine.className = "form-error";
  statusLine.setAttribute("role", "status");
  article.append(statusLine);
  workspace.append(article);

  if (!bootstrapState?.platform_admin) {
    statusLine.textContent = "A decisão de liberação comercial exige autoridade explícita de plataforma.";
    return;
  }

  try {
    const response = await api("/v1/admin/commercial-release");
    const current = response.current && typeof response.current === "object" ? response.current : null;
    const history = Array.isArray(response.history) ? response.history : [];

    const summary = document.createElement("div");
    summary.className = "grid-list";
    summary.append(
      rowElement({
        item: "Estado comercial",
        value: current?.status || "unavailable",
        status: current?.status || "UNAVAILABLE",
      }),
      rowElement({
        item: "Versão",
        value: typeof current?.version === "number" ? current.version : "—",
        status: "VERSIONED",
      }),
      rowElement({
        item: "Histórico",
        value: history.length,
        status: "AUDITED",
      }),
    );

    const form = document.createElement("form");
    form.className = "panel-form";

    const statusLabel = document.createElement("label");
    statusLabel.textContent = "Próximo estado";
    const statusSelect = document.createElement("select");
    for (const value of [
      "unavailable",
      "internal_only",
      "waitlist",
      "ready_for_checkout_configuration",
      "ready_for_commercial_review",
      "commercial_approved",
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      if ((current?.status || "unavailable") === value) option.selected = true;
      statusSelect.append(option);
    }
    statusLabel.append(statusSelect);

    const messageLabel = document.createElement("label");
    messageLabel.textContent = "Mensagem pública";
    const messageInput = document.createElement("textarea");
    messageInput.rows = 3;
    messageInput.value = typeof current?.public_message === "string" ? current.public_message : "";
    messageLabel.append(messageInput);

    const decisionLabel = document.createElement("label");
    decisionLabel.textContent = "Referência da decisão humana";
    const decisionInput = document.createElement("input");
    decisionInput.type = "text";
    decisionInput.value = typeof current?.human_decision_reference === "string"
      ? current.human_decision_reference
      : "";
    decisionInput.placeholder = "Obrigatória para commercial_approved";
    decisionLabel.append(decisionInput);

    const warning = document.createElement("p");
    warning.className = "empty-state";
    warning.textContent = "COMMERCIAL_APPROVED nunca é inferido por pricing, CI, Cakto ou readiness fiscal. Checkout e produção fiscal permanecem autoridades separadas.";

    const publish = document.createElement("button");
    publish.className = "primary";
    publish.type = "submit";
    publish.textContent = "Registrar nova decisão";

    form.append(statusLabel, messageLabel, decisionLabel, warning, publish);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      publish.disabled = true;
      statusLine.textContent = "";
      try {
        const expectedVersion = typeof current?.version === "number" ? current.version : null;
        const decision = {
          version: expectedVersion === null ? 1 : expectedVersion + 1,
          status: statusSelect.value,
          public_message: messageInput.value.trim() || null,
          human_decision_reference: decisionInput.value.trim() || null,
        };
        await api("/v1/admin/commercial-release", {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken() },
          body: JSON.stringify({
            decision,
            expected_version: expectedVersion,
          }),
        });
        await renderCommercialRelease();
      } catch (error) {
        statusLine.textContent = error instanceof Error ? error.message : "Não foi possível registrar a decisão comercial";
      } finally {
        publish.disabled = false;
      }
    });

    article.replaceChildren(summary, form, statusLine);
  } catch (error) {
    statusLine.textContent = error instanceof Error ? error.message : "Falha ao carregar a decisão comercial";
  }
}

async function renderCheckoutAdmin() {
  workspace.replaceChildren();
  const article = panel("Canais de Venda / Checkout", "Platform administration");
  const statusLine = document.createElement("p");
  statusLine.className = "form-error";
  statusLine.setAttribute("role", "status");
  article.append(statusLine);
  workspace.append(article);

  if (!bootstrapState?.platform_admin) {
    statusLine.textContent = "A configuração de canais de venda exige autoridade explícita de plataforma.";
    return;
  }

  try {
    const response = await api("/v1/admin/checkout/cakto");
    const bindings = Array.isArray(response.bindings) ? response.bindings : [];
    const summary = document.createElement("div");
    summary.className = "grid-list";

    if (!bindings.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Nenhum adapter de checkout configurado. Compra permanece fail-closed.";
      summary.append(empty);
    } else {
      for (const binding of bindings) {
        summary.append(
          rowElement({
            plano: binding.plan_id,
            oferta: binding.external_offer_id,
            status: binding.enabled ? "ENABLED" : "DISABLED",
          }),
        );
      }
    }

    const form = document.createElement("form");
    form.className = "panel-form";

    const productLabel = document.createElement("label");
    productLabel.textContent = "Cakto product ID";
    const productInput = document.createElement("input");
    productInput.required = true;
    productInput.autocomplete = "off";
    productLabel.append(productInput);

    const offerLabel = document.createElement("label");
    offerLabel.textContent = "Cakto offer ID";
    const offerInput = document.createElement("input");
    offerInput.required = true;
    offerInput.autocomplete = "off";
    offerLabel.append(offerInput);

    const planLabel = document.createElement("label");
    planLabel.textContent = "NFCore plan_id";
    const planInput = document.createElement("input");
    planInput.required = true;
    planInput.autocomplete = "off";
    planLabel.append(planInput);

    const entitlementLabel = document.createElement("label");
    entitlementLabel.textContent = "Entitlements (separados por vírgula)";
    const entitlementInput = document.createElement("input");
    entitlementInput.required = true;
    entitlementInput.autocomplete = "off";
    entitlementLabel.append(entitlementInput);

    const enabledLabel = document.createElement("label");
    const enabledInput = document.createElement("input");
    enabledInput.type = "checkbox";
    enabledInput.checked = true;
    enabledLabel.append(enabledInput, document.createTextNode(" Binding habilitado"));

    const warning = document.createElement("p");
    warning.className = "empty-state";
    warning.textContent = "Adapter ativo: Cakto. O preço deve referenciar esta oferta como cakto://PRODUCT_ID/OFFER_ID. IDs não são credenciais. Client secret, token e webhook secret nunca pertencem a este formulário.";

    const submit = document.createElement("button");
    submit.className = "primary";
    submit.type = "submit";
    submit.textContent = "Salvar binding";

    form.append(
      productLabel,
      offerLabel,
      planLabel,
      entitlementLabel,
      enabledLabel,
      warning,
      submit,
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      statusLine.textContent = "";
      try {
        const entitlementIds = entitlementInput.value
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        await api("/v1/admin/checkout/cakto", {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken() },
          body: JSON.stringify({
            external_product_id: productInput.value.trim(),
            external_offer_id: offerInput.value.trim(),
            plan_id: planInput.value.trim(),
            entitlement_ids: entitlementIds,
            enabled: enabledInput.checked,
          }),
        });
        await renderCheckoutAdmin();
      } catch (error) {
        statusLine.textContent = error instanceof Error ? error.message : "Não foi possível salvar o binding Cakto";
      } finally {
        submit.disabled = false;
      }
    });

    article.replaceChildren(summary, form, statusLine);
  } catch (error) {
    statusLine.textContent = error instanceof Error ? error.message : "Falha ao carregar o canal de venda configurado";
  }
}

/** @param {string} viewId */
/** @type {Record<string, {operation:string, permission:string, fields:[string,string,string][]}>} */
const customerForms = {
  certificates: {operation: "configureCertificates", permission: "certificate.manage", fields: [["reference_id", "Referência governada (sem material secreto)", "text"], ["kind", "Tipo: certificate, csc ou credentials", "text"], ["provider_id", "Provider (opcional para certificado)", "optional"]]},
  providers: {operation: "configureProviders", permission: "integration.manage", fields: [["binding_id", "ID do binding", "text"], ["document_kind", "Documento: nfe, nfce ou nfse", "text"], ["state_code", "UF", "text"], ["municipality_ibge_code", "Município IBGE (NFS-e)", "optional"], ["operation", "Operação: authorize, query, cancel, inutilize ou status", "text"], ["provider_id", "Provider", "text"], ["enabled", "Binding habilitado", "checkbox"]]},
  webhooks: {operation: "configureWebhooks", permission: "integration.manage", fields: [["destination_id", "ID do destino", "text"], ["url", "HTTPS público com path explícito, sem query ou credenciais", "url"], ["enabled", "Solicitar entrega após aprovação da plataforma", "checkbox"]]},
  integrations: {operation: "configureIntegrations", permission: "integration.manage", fields: [["module_id", "ID do módulo", "text"], ["enabled", "Módulo habilitado", "checkbox"]]},
  settings: {operation: "configureSettings", permission: "configuration.write", fields: [["policy_id", "ID da política", "text"], ["provider_id", "Provider", "text"], ["connect_timeout_seconds", "Timeout de conexão (segundos)", "number"], ["read_timeout_seconds", "Timeout de leitura (segundos)", "number"], ["max_attempts", "Máximo de tentativas", "number"], ["base_delay_seconds", "Espera inicial (segundos)", "number"], ["max_delay_seconds", "Espera máxima (segundos)", "number"], ["jitter_ratio", "Jitter (0 a 1)", "number"], ["circuit_failure_threshold", "Falhas para abrir circuito", "number"], ["circuit_recovery_seconds", "Recuperação do circuito (segundos)", "number"], ["circuit_success_threshold", "Sucessos para fechar circuito", "number"]]},
};

/** @param {HTMLFormElement} form @param {string} key @param {string} label @param {string} kind @returns {HTMLInputElement} */
function configurationInput(form, key, label, kind) {
  const wrapper = document.createElement("label"); wrapper.textContent = label;
  const input = document.createElement("input"); input.name = key;
  input.id = `configuration-${key}`; input.type = kind === "optional" ? "text" : kind;
  input.required = kind !== "optional" && kind !== "checkbox";
  if (kind === "number") input.step = "any";
  input.autocomplete = "off"; wrapper.append(input); form.append(wrapper);
  return input;
}

/** @param {HTMLElement} article @param {string} viewId @param {Record<string, unknown>[]} rows */
function appendCustomerConfiguration(article, viewId, rows) {
  const spec = customerForms[viewId];
  const configured = bootstrapState?.projection.customer_configuration_operations;
  if (!spec || !bootstrapState?.permissions.includes(spec.permission) || !Array.isArray(configured)
      || !configured.includes(spec.operation) || !selectedFiscalUnit) return;
  const form = document.createElement("form"); form.id = "customer-configuration-form";
  const intro = document.createElement("p");
  intro.textContent = "Alteração governada neste escopo. Informe a versão atual (0 para cadastro novo). Cadastro não comprova material secreto resolvido, entrega ou homologação. Webhook alterado aguarda nova aprovação da plataforma.";
  form.append(intro);
  const revision = configurationInput(form, "expected_version", "Versão atual", "number");
  revision.min = "0"; revision.step = "1"; revision.value = "0";
  /** @type {Map<string,HTMLInputElement>} */
  const inputs = new Map(spec.fields.map(([key, label, kind]) => [key, configurationInput(form, key, label, kind)]));
  const existing = document.createElement("select"); existing.id = "configuration-existing";
  const empty = document.createElement("option"); empty.textContent = "Novo cadastro"; empty.value = ""; existing.append(empty);
  rows.filter((row) => viewId === "certificates" || row.record_type === viewId).forEach((row, index) => {
    const option = document.createElement("option"); option.value = String(index);
    option.textContent = `${row.target_key || row.destination_id || row.binding_id || row.module_id || row.reference_kind || row.provider_id} · versão ${row.version || 0}`;
    existing.append(option);
  });
  const selectionLabel = document.createElement("label"); selectionLabel.textContent = "Editar cadastro existente";
  selectionLabel.append(existing); form.prepend(selectionLabel);
  existing.addEventListener("change", () => {
    const row = existing.value === "" ? null : rows.filter((item) => viewId === "certificates" || item.record_type === viewId)[Number(existing.value)];
    revision.value = String(row?.version || 0);
    for (const [key, input] of inputs) {
      const value = row?.[key === "kind" ? "reference_kind" : key];
      if (input.type === "checkbox") input.checked = value === true;
      else input.value = value == null ? "" : String(value);
    }
  });
  const submit = document.createElement("button"); submit.type = "submit"; submit.className = "primary";
  submit.textContent = viewId === "webhooks" ? "Solicitar destino" : "Salvar configuração";
  const result = document.createElement("p"); result.setAttribute("role", "status");
  form.append(submit, result);
  /** @type {{fingerprint:string,key:string}|null} */
  let attempt = null;
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); if (!form.reportValidity()) return;
    /** @type {Record<string,unknown>} */
    const values = {};
    for (const [key, input] of inputs) {
      if (input.type === "checkbox") values[key] = input.checked;
      else if (input.type === "number") values[key] = Number(input.value);
      else if (input.value || spec.fields.find(([field]) => field === key)?.[2] !== "optional") values[key] = input.value;
    }
    const payload = {unit_id: selectedFiscalUnit, environment: selectedFiscalEnvironment, expected_version: Number(revision.value), values};
    const fingerprint = JSON.stringify(payload);
    if (!attempt || attempt.fingerprint !== fingerprint) attempt = {fingerprint, key: crypto.randomUUID()};
    submit.disabled = true; result.textContent = "Registrando configuração…";
    try {
      const saved = await api(`/v1/portal/operations/${spec.operation}`, {method: "POST", headers: {"X-CSRF-Token": csrfToken(), "Idempotency-Key": attempt.key}, body: fingerprint});
      result.textContent = `Configuração registrada · versão ${saved.version}${saved.approval_status ? ` · aprovação ${saved.approval_status}` : ""}. Verificação operacional não confirmada.`;
      revision.value = String(saved.version); attempt = null;
    } catch (error) { result.textContent = error instanceof Error ? error.message : "Falha ao registrar configuração"; }
    finally { submit.disabled = false; }
  });
  article.append(form);
}

/** @param {HTMLElement} article */
function appendEgressReview(article) {
  if (!bootstrapState?.platform_admin) return;
  const form = document.createElement("form"); form.id = "egress-review-form";
  const tenant = configurationInput(form, "egress-tenant", "Tenant solicitado", "text");
  const unit = configurationInput(form, "egress-unit", "Unidade solicitada", "text");
  const environment = configurationInput(form, "egress-environment", "Ambiente: homologation ou production", "text");
  const destination = configurationInput(form, "egress-destination", "ID do destino solicitado", "text");
  const review = document.createElement("button"); review.type = "submit"; review.textContent = "Consultar solicitação";
  const status = document.createElement("p"); status.setAttribute("role", "status"); form.append(review, status);
  const decisionForm = document.createElement("form"); decisionForm.id = "egress-decision-form"; decisionForm.hidden = true;
  const expiry = configurationInput(decisionForm, "egress-expiry", "Validade da aprovação (ISO 8601 com fuso, até 30 dias)", "text");
  const notice = document.createElement("p"); notice.textContent = "Somente autoridade canônica da plataforma. Não aprova a própria solicitação. Não realiza tráfego ou deploy.";
  decisionForm.append(notice);
  /** @type {{url:string,version:number,path:string}|null} */
  let reviewed = null;
  /** @type {{fingerprint:string,key:string}|null} */
  let attempt = null;
  for (const [decision, label] of [["approved", "Aprovar egress"], ["revoked", "Revogar egress"]]) {
    const button = document.createElement("button"); button.type = "button"; button.textContent = label;
    button.addEventListener("click", async () => {
      if (!reviewed || (decision === "approved" && !decisionForm.reportValidity())) return;
      const payload = {url: reviewed.url, expected_version: reviewed.version, expires_at: expiry.value};
      const fingerprint = JSON.stringify([reviewed.path, decision, payload]);
      if (!attempt || attempt.fingerprint !== fingerprint) attempt = {fingerprint, key: crypto.randomUUID()};
      button.disabled = true;
      try {
        const result = await api(`${reviewed.path}/${decision}`, {method: "POST", headers: {"X-CSRF-Token": csrfToken(), "Idempotency-Key": attempt.key}, body: JSON.stringify(payload)});
        status.textContent = `Decisão ${result.approval_status} registrada · versão ${result.version}. Entrega não confirmada.`;
        reviewed.version = Number(result.version); attempt = null;
      } catch (error) { status.textContent = error instanceof Error ? error.message : "Decisão negada"; }
      finally { button.disabled = false; }
    }); decisionForm.append(button);
  }
  for (const input of [tenant, unit, environment, destination]) input.addEventListener("input", () => { reviewed = null; decisionForm.hidden = true; });
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); reviewed = null; decisionForm.hidden = true;
    const path = `/v1/portal/egress/${[tenant.value, unit.value, environment.value, destination.value].map(encodeURIComponent).join("/")}`;
    try {
      const result = await api(path);
      reviewed = {path, url: String(result.url), version: Number(result.version)};
      status.textContent = `${reviewed.url} · versão ${reviewed.version} · ${result.approval_status}. Habilitado solicitado: ${result.enabled}.`;
      decisionForm.hidden = false;
    } catch (error) { status.textContent = error instanceof Error ? error.message : "Consulta negada"; }
  }); article.append(form, decisionForm);
}

/** @returns {string[]} */
function assignableUserRoles() {
  if (bootstrapState?.role === "owner") return ["owner", "admin", "operator", "auditor", "billing"];
  if (bootstrapState?.role === "admin") return ["operator", "auditor", "billing"];
  return [];
}

/** @param {string} value @returns {string[]|null} */
function parseUserUnits(value) {
  const normalized = value.split(",").map((item) => item.trim()).filter(Boolean);
  return normalized.length ? [...new Set(normalized)] : null;
}

/** @param {HTMLElement} article @param {Record<string, unknown>[]} rows */
function appendUserAdministration(article, rows) {
  if (!bootstrapState?.permissions.includes("user.manage")) return;
  const roles = assignableUserRoles();
  if (!roles.length) return;

  const form = document.createElement("form");
  form.id = "user-administration-form";
  form.className = "panel-form";

  const intro = document.createElement("p");
  intro.textContent = "Administração baseada na autoridade da sessão. O tenant nunca vem do navegador, platform_admin não pode ser concedido aqui e alterações revogam sessões ativas.";

  const existingLabel = document.createElement("label");
  existingLabel.textContent = "Usuário";
  const existing = document.createElement("select");
  existing.id = "user-existing";
  const createOption = document.createElement("option");
  createOption.value = "";
  createOption.textContent = "Novo usuário";
  existing.append(createOption);
  rows.forEach((row, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = String(row.email || row.account_id || ("Usuário " + (index + 1)));
    existing.append(option);
  });
  existingLabel.append(existing);

  const emailLabel = document.createElement("label");
  emailLabel.textContent = "E-mail";
  const email = document.createElement("input");
  email.type = "email";
  email.autocomplete = "email";
  email.required = true;
  emailLabel.append(email);

  const roleLabel = document.createElement("label");
  roleLabel.textContent = "Papel";
  const role = document.createElement("select");
  role.id = "user-target-role";
  for (const roleName of roles) {
    const option = document.createElement("option");
    option.value = roleName;
    option.textContent = roleName.toUpperCase();
    role.append(option);
  }
  roleLabel.append(role);

  const unitsLabel = document.createElement("label");
  unitsLabel.textContent = "Unidades (separadas por vírgula; vazio = todas, quando autorizado)";
  const units = document.createElement("input");
  units.id = "user-target-units";
  units.autocomplete = "off";
  unitsLabel.append(units);

  const enabledLabel = document.createElement("label");
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = true;
  enabledLabel.append(enabled, document.createTextNode(" Conta habilitada"));

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "primary";
  submit.textContent = "Criar usuário";
  const statusLine = document.createElement("p");
  statusLine.setAttribute("role", "status");
  statusLine.className = "form-error";

  /** @type {{fingerprint:string,key:string}|null} */
  let attempt = null;

  function loadSelection() {
    const row = existing.value === "" ? null : rows[Number(existing.value)];
    email.disabled = Boolean(row);
    email.value = row ? String(row.email || "") : "";
    const rowRole = row ? String(row.role || "") : "";
    if (rowRole && roles.includes(rowRole)) role.value = rowRole;
    else role.value = roles[0];
    units.value = row && Array.isArray(row.unit_ids) ? row.unit_ids.join(", ") : "";
    enabled.checked = row ? row.enabled === true : true;
    const mutable = !row || row.mutable === true;
    role.disabled = !mutable;
    units.disabled = !mutable;
    enabled.disabled = !mutable;
    submit.disabled = !mutable;
    submit.textContent = row ? "Salvar usuário" : "Criar usuário";
    statusLine.textContent = row && !mutable
      ? "Conta visível, mas protegida contra alteração por esta autoridade."
      : row?.platform_admin === true
        ? "Autoridade de plataforma nunca é administrada por esta tela."
        : "";
    attempt = null;
  }
  existing.addEventListener("change", loadSelection);
  loadSelection();

  form.append(intro, existingLabel, emailLabel, roleLabel, unitsLabel, enabledLabel, submit, statusLine);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const row = existing.value === "" ? null : rows[Number(existing.value)];
    if (row && row.mutable !== true) return;
    const operation = row ? "updateUser" : "createUser";
    const payload = row
      ? {
          target_account_id: row.account_id,
          expected_version: Number(row.version),
          target_role: role.value,
          target_unit_ids: parseUserUnits(units.value),
          enabled: enabled.checked,
        }
      : {
          email: email.value.trim(),
          target_role: role.value,
          target_unit_ids: parseUserUnits(units.value),
        };
    const fingerprint = JSON.stringify([operation, payload]);
    if (!attempt || attempt.fingerprint !== fingerprint) {
      attempt = {fingerprint, key: crypto.randomUUID()};
    }
    submit.disabled = true;
    statusLine.textContent = "";
    try {
      const result = await api("/v1/portal/operations/" + operation, {
        method: "POST",
        headers: {"X-CSRF-Token": csrfToken(), "Idempotency-Key": attempt.key},
        body: JSON.stringify(payload),
      });
      statusLine.textContent = result.created
        ? "Usuário criado. A senha deve ser definida pelo fluxo existente de recuperação."
        : result.replay
          ? "Estado já aplicado; nenhuma duplicação foi criada."
          : "Usuário atualizado e sessões anteriores revogadas.";
      attempt = null;
      await bootstrap();
      await renderSurface("users");
    } catch (error) {
      statusLine.textContent = error instanceof Error ? error.message : "Administração de usuário rejeitada";
      submit.disabled = false;
    }
  });
  article.append(form);
}

/** @param {string} viewId */
async function renderSurface(viewId) {
  if (currentView !== viewId) fiscalPageOffset = 0;
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
  if (viewId === "webhook-egress") {
    workspace.replaceChildren();
    const egressPanel = panel(descriptions[viewId]);
    appendEgressReview(egressPanel); workspace.append(egressPanel); return;
  }
  if (viewId === "pricing-admin") {
    await renderPricingAdmin();
    return;
  }
  if (viewId === "commercial-release") {
    await renderCommercialRelease();
    return;
  }
  if (viewId === "checkout-admin") {
    await renderCheckoutAdmin();
    return;
  }
  workspace.replaceChildren();
  const article = panel(descriptions[viewId] || label);
  if (scopedViews.has(viewId)) appendFiscalFilters(article, viewId);
  const loading = document.createElement("p");
  loading.textContent = "Carregando dados autorizados...";
  article.append(loading);
  workspace.append(article);
  try {
    const filters = scopedViews.has(viewId) ? `?${new URLSearchParams({
      ...(selectedFiscalUnit ? {unit_id: selectedFiscalUnit} : {}),
      environment: selectedFiscalEnvironment, limit: "100", offset: String(fiscalPageOffset),
    })}` : "";
    const response = await api(`/v1/portal/surfaces/${encodeURIComponent(viewId)}${filters}`);
    const grid = document.createElement("div");
    grid.className = "grid-list";
    const rows = Array.isArray(response.rows) ? response.rows : [];
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = scopedViews.has(viewId) ? "Nenhum registro nesta página do escopo autorizado." : "Nenhum registro disponível neste escopo autorizado.";
      grid.append(empty);
    } else {
      for (const row of rows) grid.append(scopedViews.has(viewId) ? fiscalRowElement(row) : rowElement(row));
    }
    loading.remove();
    article.append(grid);
    if (["billing", "plans", "usage"].includes(viewId)) {
      const notice = document.createElement("p");
      notice.className = "empty-state";
      notice.textContent = "Estado lido das autoridades comerciais canônicas do NFCore. Gateways externos permanecem adapters e não definem assinatura, plano, entitlement ou uso.";
      article.append(notice);
    }
    if (configurationViews.has(viewId)) {
      const notice = document.createElement("p");
      notice.className = "form-error";
      notice.textContent = "Referência cadastrada não comprova segredo resolvido, entrega, homologação ou produção. Webhooks exigem aprovação vigente da plataforma.";
      appendCustomerConfiguration(article, viewId, rows);
      article.append(notice);
    }
    if (viewId === "onboarding") appendOnboardingControls(article);
    if (viewId === "users") appendUserAdministration(article, rows);
    if (["documents", "issuances", "reconciliation"].includes(viewId)) appendFiscalActions(article);
    if (scopedViews.has(viewId) && viewId !== "capabilities") {
      const previous = document.createElement("button");
      previous.type = "button"; previous.textContent = "Página anterior"; previous.disabled = fiscalPageOffset === 0;
      previous.addEventListener("click", () => { fiscalPageOffset = Math.max(0, fiscalPageOffset - 100); void renderSurface(viewId); });
      const next = document.createElement("button");
      next.type = "button"; next.textContent = "Próxima página";
      next.addEventListener("click", () => { fiscalPageOffset += 100; void renderSurface(viewId); });
      next.disabled = fiscalPageOffset >= 10000;
      article.append(previous, next);
    }
  } catch (error) {
    loading.textContent = error instanceof Error ? error.message : "Falha ao carregar superfície";
    loading.className = "form-error";
  }
}

/** @returns {Set<string>|null} */
function availableSurfaces() {
  const value = bootstrapState?.projection.available_surfaces;
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) return null;
  return new Set(["overview", ...value]);
}

function buildNavigation() {
  nav.replaceChildren();
  const allowed = availableSurfaces();
  for (const group of navigation) {
    const visibleItems = group.items.filter(([id]) => allowed === null || allowed.has(id));
    if (!visibleItems.length) continue;
    const section = document.createElement("section");
    section.className = "nav-group";
    const label = document.createElement("span");
    label.className = "nav-group-label";
    label.textContent = group.label;
    section.append(label);
    for (const [id, itemLabel] of visibleItems) {
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

forgotPasswordAction.addEventListener("click", showPasswordResetRequest);
passwordResetRequestCancel.addEventListener("click", showRegularLogin);
passwordResetRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  passwordResetRequestStatus.textContent = "";
  try {
    await api("/v1/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email: passwordResetEmail.value }),
    });
    passwordResetRequestStatus.textContent = "Se a conta for elegível, as instruções de recuperação serão enviadas pelo canal configurado.";
  } catch (error) {
    passwordResetRequestStatus.textContent = error instanceof Error ? error.message : "Falha ao solicitar recuperação";
  }
});

passwordResetCompleteForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  passwordResetCompleteStatus.textContent = "";
  const resetToken = pendingPasswordResetToken;
  if (!resetToken) {
    passwordResetCompleteStatus.textContent = "Link de recuperação inválido.";
    return;
  }
  try {
    await api("/v1/auth/password-reset/complete", {
      method: "POST",
      body: JSON.stringify({
        reset_token: resetToken,
        new_password: passwordResetNewPassword.value,
      }),
    });
    passwordResetNewPassword.value = "";
    pendingPasswordResetToken = null;
    showRegularLogin();
    showLogin("Senha alterada. Entre novamente com a nova senha.");
  } catch (error) {
    if (passwordResetErrorCode(error) === "PASSWORD_RESET_NOT_USABLE") {
      pendingPasswordResetToken = null;
    }
    passwordResetCompleteStatus.textContent = passwordResetErrorMessage(error);
  }
});

logoutAction.addEventListener("click", async () => {
  try {
    await api("/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken() } });
  } finally {
    bootstrapState = null;
    pendingFiscalRequest = null;
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
    const payload = { ...parsed, unit_id: unitId, environment: selectedFiscalEnvironment };
    const fingerprint = `${selected}:${JSON.stringify(payload)}`;
    const mutation = selected !== "queryFiscalDocument";
    /** @type {Record<string,string>} */
    const headers = { "X-CSRF-Token": csrfToken() };
    if (mutation) {
      if (pendingFiscalRequest && pendingFiscalRequest.fingerprint !== fingerprint) {
        throw new Error("Há uma tentativa pendente com outro conteúdo. Preserve o pedido original até confirmar seu resultado.");
      }
      pendingFiscalRequest ||= {fingerprint, key: crypto.randomUUID()};
      headers["Idempotency-Key"] = pendingFiscalRequest.key;
    }
    await api(`/v1/portal/operations/${encodeURIComponent(selected)}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    pendingFiscalRequest = null;
    operationDialog.close();
    await renderSurface(currentView);
  } catch (error) {
    operationError.textContent = error instanceof Error ? error.message : "Operação rejeitada";
  }
});

if (pendingPasswordResetToken) {
  showPasswordResetCompletion();
} else {
  void bootstrap();
}
