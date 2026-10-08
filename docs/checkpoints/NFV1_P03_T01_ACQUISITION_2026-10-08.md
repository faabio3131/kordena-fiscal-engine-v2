# NFV1-P03-T01 — aquisição first-party no runtime

Estado: EM EXECUCAO. Implementação/testes/publicação Draft autorizados pelo dono
em 2026-10-08. Merge/deploy/transação real não incluídos nesta autorização.

## CURRENT e escopo

Baseline main `a5b8edcb637b53c66995a039494eded4f5b0c6fa`, árvore
`fade0b6fcccdd0c3ca65e338961c62850fc0be00`, CI #679/Governance #100 SUCCESS.
T07/P2 internos certificados pelo closeout integrado #132; primeira tarefa aberta
NFV1-P03-T01. Nenhuma execução de T02..T05.

A composição em `create_runtime_app` já reutiliza CommercialAcquisitionService,
WebhookSecurity, FixedWindowRateLimiter, catálogo/release e o banco PostgreSQL
canônicos. Fulfillment/provisioning/activation são os mesmos serviços do runtime.
Não há nova autoridade, preço operacional, contrato de dados pessoais ou auth.
O endpoint POST `/v1/commercial/acquisitions` só é montado com persistência,
composição, projector/starter do mesmo provider e security explícita.

## Correção e prova

Lacuna: a oferta podia expor purchase_enabled e URLs de checkout com processamento
configurado, mas sem o endpoint autenticado composto. A montagem da oferta agora
condiciona esse caminho à presença da aquisição composta. O gate comercial
existente continua exigindo pricing/release/checkout/processamento e toda a cadeia
de entrega. Provider/secret operacionais não são inferidos dessa composição.

Testes novos em `tests/runtime/test_p03_t01_acquisition.py`:

- wiring: falta de assinatura configurada/starter e mismatch de provider bloqueiam
  oferta e deixam o endpoint ausente;
- PostgreSQL real no CI: HTTP assinado, persistência, mesmo ID/expiração após
  reinício, conflito de payload, expiração e revogação de release;
- ausência de pricing/release/processamento/activation bloqueia sem persistência;
- assinatura adulterada, payload com autoridade do browser e rate limit;
- perda de resposta do checkout reutiliza a referência já persistida;
- falha de escrita impede iniciar checkout; retry após recuperação;
- aquisição não cria organização, conta OWNER, compra, subscription ou reset.

Ruff, Mypy strict e plan validator locais PASS. Testes dirigidos locais:12 PASS,
13 SKIP exclusivamente por ausência de PostgreSQL local. Não são prova de
PostgreSQL nem integração externa. CI remoto deve executar todos sem SKIP antes
de tornar esta tarefa revisável para integração. Suite integral local/CI pendentes.

## Limites e pendências

Checkout, chave e entrega usados nos testes são sintéticos. PostgreSQL no CI é
persistência real; isso não certifica provider, secret client ou entrega operacional.
A inicialização padrão permanece bloqueada sem dependências explícitas. Resolução
do secret/receiver operacional pertence a T03; gate completo de purchase readiness
T04; lifecycle T05; staging drift STG-B01..B08 mantém owners P4/P5/P9/P11.
Nenhum segredo real acessado, deploy realizado ou pagamento efetuado.

Prova de PR/HEAD/CI será registrada no corpo da PR após publicação, evitando SHA
circular no commit. Ledger permanece em execução até integração autorizada,
gates de main e closeout persistente.
