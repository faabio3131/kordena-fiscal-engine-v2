# V2-16.6 — Onboarding de novos produtos via Product Contract Pack

Data: 2026-09-13

## Objetivo

Tornar repetível e certificável a integração de futuros produtos FM sem criar uma segunda fonte de verdade fiscal e sem alterar o núcleo para cada SaaS consumidor.

A infraestrutura existente continua sendo a base: `ProductContractPackDescriptor`, `ProductUseCaseDescriptor`, `ProductContractPackRegistry`, catálogo explícito, contratos de integração e Capability & Readiness API.

A V2-16.6 adiciona apenas duas peças reutilizáveis:

1. **certificação estrutural de onboarding** — comprova que o produto declarou contrato, autoridade comercial e estratégia de idempotência;
2. **pre-flight fail-closed de mutação** — impede mutação quando pack/use case/host/operação/documento/ação/escopo/idempotência/binding/capability/readiness não estiverem explícitos e válidos.

Nenhuma dessas peças decide imposto, provider, jurisdição, binding ou readiness.

## Checklist mínimo obrigatório

Um novo produto precisa declarar e certificar:

1. `product_id`;
2. `pack_id`;
3. `host_namespace`;
4. versão do pack;
5. um ou mais use cases;
6. operation kinds permitidos;
7. document kinds permitidos;
8. fiscal actions e, quando aplicável, vertical capabilities;
9. eventos inbound/outbound;
10. fato comercial autoritativo (`commercial_authority`);
11. estratégia de idempotência;
12. registro explícito no catálogo antes do uso real;
13. escopo fiscal completo em runtime;
14. binding fiscal resolvido por autoridade própria;
15. capability/readiness autoritativos antes de mutação;
16. contract tests e regressão verde.

## Fluxo recomendado

1. Modelar o Product Contract Pack sem importar modelos privados do SaaS.
2. Declarar qual fato do SaaS é autoridade comercial real; não usar eventos aproximados.
3. Declarar a estratégia determinística de idempotência.
4. Executar `certify_product_onboarding(...)`.
5. Adicionar o pack ao catálogo governado somente após revisão/testes.
6. No runtime consumidor, formar o handoff com fatos de negócio.
7. Antes de mutação no Bridge, executar `validate_product_mutation_preflight(...)` usando binding/capability/readiness provenientes das respectivas autoridades.
8. Somente então chamar a operação fiscal permitida.

## Fail-closed

O onboarding/pre-flight rejeita ou deve rejeitar antes de mutação:

- pack não registrado;
- host namespace desconhecido ou pertencente a outro pack;
- use case inexistente;
- operation kind incompatível;
- document kind incompatível;
- fiscal action não declarada;
- escopo incompleto;
- host do scope divergente;
- idempotency key ausente;
- binding fiscal não resolvido;
- capability não concedida;
- readiness não concedido.

Vertical capabilities declaradas também devem ser validadas contra o `VerticalModuleRegistry`; não são silenciosamente ignoradas.

## Exemplo sintético de certificação

A suíte `tests/test_v2_16_product_pack_onboarding.py` usa um pack sintético `synthetic-product` apenas como prova arquitetural. Ele não representa cliente ou produto comercial real e não é adicionado ao catálogo global.

A certificação estrutural produz explicitamente `readiness_granted = False`. Portanto passar no onboarding jamais equivale a homologação ou produção.

O pre-flight sintético só passa quando recebe explicitamente escopo, binding, capability e readiness como já resolvidos. Testes negativos certificam o fechamento para inputs incompatíveis.

## O que NÃO fazer

- não inferir pagamento/settlement a partir do nome do produto;
- não colocar regra estadual/municipal/provider no SaaS consumidor;
- não registrar pack automaticamente por fallback;
- não escolher documento por heurística permissiva;
- não tratar certificação estrutural como `PRODUCTION_APPROVED`;
- não criar produto sintético no catálogo real;
- não bypassar a Capability & Readiness API.

## Decisão arquitetural

A V2-16.6 não cria um framework novo. Ela industrializa o caminho que já existia e fecha a lacuna entre “descriptor válido” e “produto pronto para tentar uma mutação fiscal governada”, mantendo cada autoridade no seu domínio.
