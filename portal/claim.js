export {};
// First-party anonymous post-payment claim. Mirrors trial.js: anonymous, no cookies,
// no Authorization header, credentials omitted. The canonical API (POST
// /v1/commercial/claim) owns token validity, idempotency and activation.
//
// Security contract for this page:
//  - The raw claim token only ever lives in the URL *fragment* (`#claim=...`), which
//    browsers never send to the server on the initial page load/request.
//  - The fragment is read once, in-memory, and immediately stripped from the visible
//    URL/history so it never lingers in browser history, referrer headers, analytics
//    or screenshots.
//  - The token is sent to the API only inside the JSON POST body, never as part of a
//    URL, never logged, never echoed back into the DOM.

/** @template {HTMLElement} T @param {string} id @returns {T} */
function element(id) {
  const value = document.getElementById(id);
  if (!value) throw new Error(`Missing claim element: ${id}`);
  return /** @type {T} */ (value);
}
const form = /** @type {HTMLFormElement} */ (element('claim-form'));
const fields = /** @type {HTMLFieldSetElement} */ (element('claim-fields'));
const legalName = /** @type {HTMLInputElement} */ (element('claim-legal-name'));
const status = element('claim-status');
const result = element('claim-result');

/** @returns {string|null} */
function claimTokenFromLocation() {
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const token = fragment.get('claim');
  return token && token.trim() ? token : null;
}

function clearClaimTokenFromLocation() {
  const url = new URL(window.location.href);
  const fragment = new URLSearchParams(url.hash.replace(/^#/, ''));
  fragment.delete('claim');
  const remainingFragment = fragment.toString();
  url.hash = remainingFragment ? `#${remainingFragment}` : '';
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
}

// Capture once, before anything else touches the URL, then strip it immediately.
const claimToken = claimTokenFromLocation();
if (claimToken) clearClaimTokenFromLocation();

let busy = false;
let completed = false;

if (!claimToken) {
  status.textContent = 'Link de confirmação inválido ou incompleto. Verifique o e-mail recebido após o pagamento.';
} else {
  status.textContent = 'Confirme os dados abaixo para concluir a ativação.';
  form.hidden = false;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy || completed || !claimToken || !form.reportValidity()) return;
  busy = true;
  fields.disabled = true;
  result.textContent = 'Enviando confirmação…';
  try {
    const response = await fetch('/v1/commercial/claim', {
      method: 'POST',
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ claim_token: claimToken, legal_name: legalName.value.trim() }),
      signal: AbortSignal.timeout(15000),
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 200 && payload && payload.status === 'activated') {
      completed = true;
      form.hidden = true;
      status.textContent = 'Compra confirmada';
      result.textContent = 'Ativação concluída. Enviamos as instruções de acesso para o e-mail da compra.';
      return;
    }
    if (response.status === 202 && payload && payload.status === 'manual_review') {
      completed = true;
      form.hidden = true;
      status.textContent = 'Em análise';
      result.textContent = 'Recebemos sua confirmação e ela está em revisão manual. Você será avisado por e-mail assim que for concluída.';
      return;
    }
    if (response.status === 409) {
      // The API never distinguishes not-found/expired/already-used; neither does this page.
      result.textContent = 'Este link de confirmação não é válido, já expirou ou já foi utilizado. Verifique se há um e-mail mais recente ou entre em contato com o suporte.';
      return;
    }
    if (response.status === 400 || response.status === 415) {
      result.textContent = 'Não foi possível validar os dados informados. Confira a razão social e tente novamente.';
      return;
    }
    if (response.status === 503) {
      result.textContent = 'Serviço temporariamente indisponível. Tente novamente em instantes com os mesmos dados.';
      return;
    }
    throw new Error('claim unavailable');
  } catch {
    result.textContent = 'Não foi possível confirmar a compra agora. Tente novamente com os mesmos dados.';
  } finally {
    busy = false;
    fields.disabled = completed;
  }
});
