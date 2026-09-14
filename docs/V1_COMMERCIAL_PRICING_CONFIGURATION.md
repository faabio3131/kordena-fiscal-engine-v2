# FM Fiscal V1.0 — Commercial Pricing Configuration

Status: **V1 COMMERCIAL POLICY**

## Regra central

Preço, plano, pacote, promoção e condição comercial são **configuração**, não código fiscal.

A FM Tecnologia deve conseguir alterar a oferta comercial sem commit, sem mudança de regra fiscal e sem deploy específico por cliente, desde que os recursos vendidos já existam na plataforma.

## O que é configurável

- planos comerciais e seus nomes de exibição;
- edição/capabilities associadas ao plano;
- preço mensal, trimestral, semestral, anual ou one-time;
- componente fixo, preço por documento e taxa de setup;
- trial em dias;
- add-ons opcionais;
- pacotes que combinam plano + add-ons;
- promoções percentuais;
- promoções por valor fixo;
- dias extras de trial;
- cupom opcional;
- início e fim de campanha;
- promoções empilháveis ou exclusivas;
- preço negociado por tenant/cliente;
- vigência do preço negociado;
- referência de contrato comercial;
- referência externa do preço no gateway/checkout;
- ativação/desativação sem apagar histórico.

## Versionamento

`CommercialPricingConfiguration.version` é monotônico.

A publicação usa optimistic versioning:

- primeira configuração: versão `1`;
- próxima publicação: versão anterior + 1;
- uma alteração baseada em versão antiga é rejeitada.

Isso evita que duas alterações comerciais concorrentes sobrescrevam uma à outra silenciosamente.

## Promoções

Promoções podem ter janela de vigência e cupom. Uma promoção marcada como não empilhável é exclusiva. Se duas promoções exclusivas estiverem ativas para o mesmo preço ao mesmo tempo, a resolução falha de forma explícita em vez de escolher arbitrariamente.

## Preço especial por cliente

`TenantPriceOverride` permite contrato enterprise, condição de lançamento ou negociação individual sem criar fork do produto.

O override pode substituir:

- mensalidade/base;
- preço por documento;
- setup.

Pode ter janela de vigência e referência do contrato, mas não contém segredo de pagamento.

## Gateway / Cakto

O catálogo guarda `external_price_reference`, não credenciais. Quando a conta comercial/gateway estiver definida, cada preço poderá apontar para o identificador correspondente na plataforma externa.

Credenciais e secrets continuam fora do Git/VCS.

## Separação de autoridade

Pricing/billing não concede autoridade fiscal. Alterar preço, plano, trial ou promoção nunca:

- homologa NF-e/NFC-e/NFS-e;
- ativa produção;
- aprova certificado;
- altera estado fiscal já constituído.

## Operação esperada

Fluxo normal de uma campanha comercial:

1. criar nova versão do catálogo;
2. adicionar/alterar preço, promoção ou pacote;
3. validar referências e conflitos;
4. publicar a nova versão;
5. sincronizar a referência externa com o gateway quando aplicável;
6. preservar a versão anterior para auditoria/reprodução histórica.

Não é necessário alterar código para a operação comercial normal.
