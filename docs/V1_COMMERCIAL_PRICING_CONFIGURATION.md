# FM Fiscal V1.0 — Commercial Pricing Configuration

Status: **V1 COMMERCIAL POLICY**

## Regra central

Preço, plano, pacote, promoção e condição comercial são **configuração administrativa, não código fiscal**.

A FM Tecnologia deve conseguir alterar a oferta comercial sem commit, sem mudança de regra fiscal e sem deploy específico por cliente, desde que os recursos vendidos já existam na plataforma.

**Nenhum preço comercial definitivo deve ficar hardcoded no código-fonte, frontend, imagem de container ou regra fiscal.** Valores presentes em testes/fixtures/exemplos são exclusivamente sintéticos e não constituem preço comercial publicado.

## Autoridade administrativa de pricing

A publicação ou alteração do catálogo de preços é uma função de **administração global da plataforma FM**, não uma permissão do cliente/tenant.

A boundary canônica de escrita é `CommercialPricingAdministrationService`. Ela exige simultaneamente:

- `AdminPrincipal` válido;
- permissão `commercial_config.write`;
- `global_scope=True`.

Um administrador limitado a um tenant, inclusive um proprietário/OWNER do cliente, não pode publicar preços globais mesmo que possua alguma permissão comercial de tenant.

A identidade concreta que recebe essa autoridade é definida pelo IAM administrativo da FM e **não deve ser hardcoded por nome, e-mail ou usuário no código**. Em produção, a política operacional deve conceder essa autoridade somente à conta administrativa designada pela direção da FM Tecnologia.

A leitura do catálogo publicado pode alimentar site, checkout e portal, mas a escrita deve permanecer atrás da boundary administrativa global.

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

Toda interface administrativa futura deve preservar esse mecanismo e apresentar conflito de versão ao administrador em vez de sobrescrever silenciosamente outra alteração.

## Persistência e painel administrativo

O modelo de pricing já é data-driven e a boundary de autorização administrativa é obrigatória. A superfície administrativa produtiva deve persistir o catálogo/versionamento em armazenamento durável e permitir alterar os valores sem editar fonte.

Enquanto essa superfície produtiva ainda não estiver composta, **não utilizar arquivo-fonte, fixture, JSON versionado no Git ou constante de frontend como substituto do painel administrativo**.

A implementação do painel/CRUD produtivo deve:

1. carregar o catálogo atual de armazenamento durável;
2. criar uma nova versão ao publicar alterações;
3. registrar ator, horário e versão para auditoria;
4. permitir ativação/desativação e vigência sem apagar histórico;
5. impedir escrita por tenant/cliente;
6. alimentar consumidores por leitura do catálogo publicado, nunca por preço duplicado/hardcoded.

## Promoções

Promoções podem ter janela de vigência e cupom. Uma promoção marcada como não empilhável é exclusiva. Se duas promoções exclusivas estiverem ativas para o mesmo preço ao mesmo tempo, a resolução falha de forma explícita em vez de escolher arbitrariamente.

## Preço especial por cliente

`TenantPriceOverride` permite contrato enterprise, condição de lançamento ou negociação individual sem criar fork do produto.

O override pode substituir:

- mensalidade/base;
- preço por documento;
- setup.

Pode ter janela de vigência e referência do contrato, mas não contém segredo de pagamento.

Overrides também são administrados pela autoridade da plataforma; não são campos de self-service do cliente.

## Gateway / Cakto

O catálogo guarda `external_price_reference`, não credenciais. Quando a conta comercial/gateway estiver definida, cada preço poderá apontar para o identificador correspondente na plataforma externa.

Credenciais e secrets continuam fora do Git/VCS.

O identificador externo deve ser configurável junto ao catálogo. Uma mudança de preço não pode exigir alteração do código do site ou do NFCORE; quando o gateway exigir nova oferta/price ID, apenas a referência configurada deve mudar após validação administrativa.

## Separação de autoridade

Pricing/billing não concede autoridade fiscal. Alterar preço, plano, trial ou promoção nunca:

- homologa NF-e/NFC-e/NFS-e;
- ativa produção;
- aprova certificado;
- altera estado fiscal já constituído.

## Operação esperada

Fluxo normal de uma campanha comercial:

1. acessar a área administrativa de pricing com autoridade global;
2. carregar a versão atual;
3. criar nova versão do catálogo;
4. adicionar/alterar preço, promoção ou pacote;
5. validar referências e conflitos;
6. publicar a nova versão;
7. sincronizar a referência externa com o gateway quando aplicável;
8. preservar a versão anterior para auditoria/reprodução histórica.

**Não é necessário alterar código para a operação comercial normal.**

## Estado antes do estudo de mercado

Até que a pesquisa competitiva e a decisão empresarial de preços sejam concluídas, o NFCORE não deve assumir nenhum valor comercial real como default de produção.

A ausência de preço aprovado é um estado comercial válido. O sistema deve permanecer preparado para receber o catálogo posteriormente pelo painel administrativo, sem exigir novo desenvolvimento ou alteração do código-fonte.
