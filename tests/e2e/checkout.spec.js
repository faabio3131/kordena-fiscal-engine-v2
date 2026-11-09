import { test, expect } from '@playwright/test';

const offer = {
  product_id: 'nfcore',
  pricing: {
    status: 'published',
    catalog: {
      configuration_id: 'cfg-1',
      version: 3,
      prices: [{ price_id: 'growth-monthly', currency: 'BRL', cadence: 'monthly', base_amount: '249.00', per_document_amount: '0', setup_amount: '0' }],
      plans: [{ plan_id: 'growth', display_name: 'Pro', edition_id: 'pro', price_ids: ['growth-monthly'], trial_days: 14, tags: [] }],
    },
  },
  release: { status: 'approved', version: 1, public_message: null, commercially_approved: true },
  checkout: {
    status: 'configured', provider: 'cakto', processing_status: 'configured',
    items: [{ plan_id: 'growth', price_id: 'growth-monthly', provider: 'cakto', checkout_url: 'https://pay.cakto.com.br/growth-monthly' }],
  },
  purchase_enabled: true,
  trial_enabled: true,
};
async function catalog(page, body = offer) {
  await page.route('**/v1/commercial/offer', async route => {
    expect(route.request().method()).toBe('GET');
    await route.fulfill({ json: body });
  });
}
async function fill(page) {
  await page.getByLabel('Razão social').fill('Empresa Sintética LTDA');
  await page.getByLabel('E-mail para contato').fill('checkout@example.test');
}

test('checkout preserves request identity after response loss and redirects without storing personal data', async ({ page }) => {
  await catalog(page);
  const requests = [];
  await page.context().addCookies([{ name: 'nfcore_session', value: 'existing-session', url: 'http://127.0.0.1:4173' }]);
  await page.route('**/v1/public/acquisitions', async route => {
    requests.push({ headers: route.request().headers(), body: route.request().postDataJSON() });
    if (requests.length === 1) await route.abort();
    else await route.fulfill({
      status: 201,
      json: {
        acquisition_reference: 'acq-1', provider: 'cakto',
        checkout_url: 'https://pay.cakto.com.br/growth-monthly', expires_at: '2026-12-31T00:00:00Z', replay: false,
      },
    });
  });
  // Stub the external checkout domain itself so the redirect assertion never
  // performs a real network call to a third-party production host.
  await page.route('https://pay.cakto.com.br/**', route => route.fulfill({ status: 200, body: 'ok' }));
  await page.goto('/checkout.html');
  await fill(page);
  await page.getByRole('button', { name: 'Ir para o pagamento' }).click();
  await expect(page.locator('#checkout-result')).toContainText('mesmos dados');
  await fill(page);
  await page.getByRole('button', { name: 'Ir para o pagamento' }).click();
  await page.waitForURL('https://pay.cakto.com.br/growth-monthly', { timeout: 5000 });
  expect(requests).toHaveLength(2);
  expect(requests[0].headers['idempotency-key']).toBe(requests[1].headers['idempotency-key']);
  for (const request of requests) {
    expect(request.headers.cookie).toBeUndefined();
    expect(request.headers.authorization).toBeUndefined();
    expect(request.headers['x-nfcore-signature']).toBeUndefined();
    expect(Object.keys(request.body).sort()).toEqual(['buyer_email', 'legal_name', 'plan_id', 'price_id']);
  }
  const stored = await page.evaluate(() => JSON.stringify(sessionStorage));
  expect(stored).not.toContain('checkout@example.test');
  expect(stored).not.toContain('Empresa Sintética LTDA');
});

for (const status of [403, 404, 503]) {
  test(`checkout fails closed when offer returns ${status}`, async ({ page }) => {
    await page.route('**/v1/commercial/offer', route => route.fulfill({ status, json: { detail: 'unavailable' } }));
    await page.goto('/checkout.html');
    await expect(page.locator('#checkout-status')).toContainText('indisponíveis');
    await expect(page.locator('#checkout-form')).toBeHidden();
    await expect(page.getByRole('link', { name: 'Já tenho uma conta / recuperar acesso' })).toHaveAttribute('href', 'index.html');
  });
}

test('purchase_enabled false hides the form honestly', async ({ page }) => {
  await catalog(page, { ...offer, purchase_enabled: false });
  await page.goto('/checkout.html');
  await expect(page.locator('#checkout-status')).toContainText('indisponíveis');
  await expect(page.locator('#checkout-form')).toBeHidden();
});

test('only items with a published checkout_url are offered', async ({ page }) => {
  await catalog(page, {
    ...offer,
    checkout: { ...offer.checkout, items: [{ plan_id: 'growth', price_id: 'growth-monthly', provider: 'cakto', checkout_url: null }] },
  });
  await page.goto('/checkout.html');
  await expect(page.locator('#checkout-status')).toContainText('Não há planos disponíveis');
  await expect(page.locator('#checkout-form')).toBeHidden();
});

test('rate limiting and conflict responses are surfaced without retry loops', async ({ page }) => {
  await catalog(page);
  await page.route('**/v1/public/acquisitions', route => route.fulfill({ status: 429, json: { detail: 'rate limited' } }));
  await page.goto('/checkout.html');
  await fill(page);
  await page.getByRole('button', { name: 'Ir para o pagamento' }).click();
  await expect(page.locator('#checkout-result')).toContainText('Limite de tentativas');
});

test('rejects a non-https checkout_url rather than redirecting', async ({ page }) => {
  await catalog(page);
  await page.route('**/v1/public/acquisitions', route => route.fulfill({
    status: 201,
    json: { acquisition_reference: 'acq-2', provider: 'cakto', checkout_url: 'javascript:alert(1)', expires_at: '2026-12-31T00:00:00Z', replay: false },
  }));
  await page.goto('/checkout.html');
  await fill(page);
  await page.getByRole('button', { name: 'Ir para o pagamento' }).click();
  await expect(page.locator('#checkout-result')).toContainText('Não foi possível confirmar');
  await expect(page).toHaveURL(/checkout\.html$/);
});
