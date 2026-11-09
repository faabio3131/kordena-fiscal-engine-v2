export {};
// First-party anonymous intake for the paid checkout bridge. The canonical
// API owns pricing, release approval and checkout authority; this page only
// renders the already-published public catalog and starts an acquisition.
/** @template {HTMLElement} T @param {string} id @returns {T} */
function element(id) {
  const value = document.getElementById(id);
  if (!value) throw new Error(`Missing checkout element: ${id}`);
  return /** @type {T} */ (value);
}
const form = /** @type {HTMLFormElement} */ (element('checkout-form'));
const fields = /** @type {HTMLFieldSetElement} */ (element('checkout-fields'));
const select = /** @type {HTMLSelectElement} */ (element('checkout-price'));
const email = /** @type {HTMLInputElement} */ (element('checkout-email'));
const legalName = /** @type {HTMLInputElement} */ (element('checkout-name'));
const status = element('checkout-status');
const result = element('checkout-result');
const offer = element('checkout-offer');
const reload = /** @type {HTMLButtonElement} */ (element('checkout-reload'));
/** @typedef {{plan_id: string, price_id: string, display_name: string, currency: string, cadence: string, base_amount: string}} CheckoutOption */
/** @type {CheckoutOption[]} */
let options = [];
let busy = false;
let completed = false;
// Keep only a digest and random request key in tab storage; never name/email.
const storageKey = 'nfcore.public-acquisition.request.v1';
/** @type {{digest: string, key: string} | null} */
let attempt = null;
try {
  const stored = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
  if (stored && /^[a-f0-9]{64}$/.test(stored.digest) &&
      /^acquisition-[a-f0-9-]{36}$/.test(stored.key)) attempt = stored;
} catch { /* Storage unavailable: retain in-memory recovery within this page. */ }

const CADENCE_LABEL = /** @type {Record<string, string>} */ ({
  monthly: '/mês', semiannual: '/semestre', annual: '/ano',
});

/** @param {CheckoutOption} opt @returns {string} */
function formatOption(opt) {
  const cadence = CADENCE_LABEL[opt.cadence] || `/${opt.cadence}`;
  const amount = Number(opt.base_amount);
  const price = Number.isFinite(amount)
    ? amount.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : opt.base_amount;
  return `${opt.display_name} · ${opt.currency} ${price}${cadence}`;
}
function showOffer() {
  const opt = options[Number(select.value)];
  offer.textContent = opt ? 'Você será redirecionado ao pagamento seguro após confirmar os dados.' : '';
}
async function loadOffer() {
  if (busy || completed) return;
  busy = true;
  form.hidden = true;
  reload.hidden = true;
  status.textContent = 'Consultando planos disponíveis…';
  try {
    const response = await fetch('/v1/commercial/offer', {
      method: 'GET', credentials: 'omit', cache: 'no-store',
      redirect: 'error', signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error('offer unavailable');
    const payload = await response.json();
    if (!payload || payload.purchase_enabled !== true) throw new Error('purchase disabled');
    const catalog = payload.pricing && payload.pricing.catalog;
    const items = payload.checkout && Array.isArray(payload.checkout.items) ? payload.checkout.items : [];
    if (!catalog || !Array.isArray(catalog.plans) || !Array.isArray(catalog.prices)) {
      throw new Error('invalid catalog');
    }
    const pricesById = new Map(catalog.prices.map((/** @type {{price_id: string}} */ price) => [price.price_id, price]));
    const checkoutReady = new Set(
      items.filter((/** @type {{checkout_url: unknown}} */ item) => typeof item.checkout_url === 'string' && item.checkout_url)
        .map((/** @type {{plan_id: string, price_id: string}} */ item) => `${item.plan_id}::${item.price_id}`)
    );
    /** @type {CheckoutOption[]} */
    const next = [];
    for (const plan of catalog.plans) {
      for (const priceId of plan.price_ids) {
        if (!checkoutReady.has(`${plan.plan_id}::${priceId}`)) continue;
        const price = pricesById.get(priceId);
        if (!price) continue;
        next.push({
          plan_id: plan.plan_id, price_id: priceId, display_name: plan.display_name,
          currency: price.currency, cadence: price.cadence, base_amount: price.base_amount,
        });
      }
    }
    options = next;
    select.replaceChildren();
    options.forEach((opt, index) => {
      const node = document.createElement('option');
      node.value = String(index);
      node.textContent = formatOption(opt);
      select.append(node);
    });
    status.textContent = options.length ? 'Selecione o plano para continuar.' : 'Não há planos disponíveis para contratação no momento.';
    form.hidden = !options.length;
    reload.hidden = !!options.length;
    showOffer();
  } catch {
    status.textContent = 'Os planos de contratação estão indisponíveis no momento. Tente novamente mais tarde.';
    reload.hidden = false;
  } finally { busy = false; }
}
select.addEventListener('change', showOffer);
reload.addEventListener('click', () => { void loadOffer(); });
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy || completed || !form.reportValidity()) return;
  const opt = options[Number(select.value)];
  if (!opt) return;
  busy = true;
  fields.disabled = true;
  result.textContent = 'Enviando solicitação…';
  const body = JSON.stringify({
    plan_id: opt.plan_id, price_id: opt.price_id,
    buyer_email: email.value.trim().toLowerCase(), legal_name: legalName.value.trim(),
  });
  try {
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body))))
      .map((byte) => byte.toString(16).padStart(2, '0')).join('');
    if (!attempt || attempt.digest !== digest) {
      attempt = { digest, key: `acquisition-${crypto.randomUUID()}` };
    }
    try { sessionStorage.setItem(storageKey, JSON.stringify(attempt)); } catch { /* In-memory retry remains safe. */ }
    const response = await fetch('/v1/public/acquisitions', {
      method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': attempt.key },
      body, signal: AbortSignal.timeout(15000),
    });
    if (response.status === 429) {
      result.textContent = 'Limite de tentativas atingido. Aguarde antes de tentar novamente.';
      return;
    }
    if (response.status === 409) {
      result.textContent = 'Não foi possível iniciar esta contratação. Confira os dados e o plano escolhido.';
      return;
    }
    if (!response.ok) throw new Error('acquisition unavailable');
    const payload = await response.json();
    if (typeof payload.checkout_url !== 'string' || !/^https:\/\//.test(payload.checkout_url)) {
      throw new Error('invalid checkout url');
    }
    completed = true;
    form.hidden = true;
    status.textContent = 'Solicitação recebida';
    result.textContent = 'Redirecionando para o pagamento seguro…';
    form.reset();
    window.location.assign(payload.checkout_url);
  } catch {
    result.textContent = 'Não foi possível confirmar a solicitação. Tente novamente com os mesmos dados para recuperar o resultado com segurança.';
  } finally {
    busy = false;
    fields.disabled = completed;
  }
});
void loadOffer();
