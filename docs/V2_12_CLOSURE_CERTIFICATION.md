# V2-12 — CLOSURE CERTIFICATION

Status: **CONCLUÍDA / CERTIFICADA**  
Branch: `v2/production-adapters`  
PR: `#13` — deve permanecer Draft  
Base V2-11: `0439246151c7edc959615361c0275961e11c3af0`

## Escopo certificado

A V2-12 certifica os boundaries de runtime necessários para Gateway/Signer/Vault sem acoplamento a fornecedor único e sem uso de segredo, certificado, CSC, credencial ou endpoint produtivo real.

Blocos certificados:

1. Vault/KMS abstraction + Secret Resolution Boundary;
2. Signer Boundary + assinatura por SecretReference;
3. Provider/Gateway adapters + CSC/Credentials;
4. Resilience Runtime;
5. Homologation Gates + Cross-provider;
6. End-to-End Certification + auditoria e fechamento.

## Gates

| Bloco | SHA | Run / Job | Resultado |
|---|---|---|---|
| B1 | `961ee84aa28f58ce933d2dd899bfd013c801da1c` | `34758902465` / `103728060621` | 88 source / 447 PASS |
| B2 | `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92` | `34759157421` / `103728746009` | 91 source / 459 PASS |
| B3 | `42f27c67145d2d4469374596d869ffc3ba05f013` | `34760113452` / `103731343836` | 93 source / 471 PASS |
| B4 | `a3db491049d6058753ebad18d6fb62026310b1b8` | `34760627774` / `103732719543` | 95 source / 483 PASS |
| B5 | `ae9347b2f97f6984e22f6a719eec5e4b1ea8a3db` | `34760988165` / `103733669977` | 97 source / 497 PASS |
| B6 funcional | `b7bccf2babed336941d920eed73cd0699e6939d4` | `34762735800` / `103738293942` | Ruff/Mypy PASS; 97 source / 508 PASS em 5.06s |

## Achado de auditoria B6 e correção

A certificação final detectou antes do fechamento que CREDENTIALS/CSC runtime estavam isolados por host/tenant/unit/environment/kind, mas ainda não por provider. Isso foi corrigido sem ampliar o schema do Control Plane:

- provider-scoped purposes exigem `provider_id` explícito;
- Vault runtime indexa CREDENTIALS/CSC por `(host, reference_id, provider_id)`;
- não existe fallback cross-provider;
- provider sem slot exato falha fechado antes do transport;
- certificate material para signer continua provider-independent;
- SQLite continua guardando somente a referência opaca e metadados de escopo.

A suíte final certifica esse isolamento com dois providers distintos e com tentativa de acesso de provider sem slot.

## End-to-end certificado

Foram certificados com material exclusivamente sintético e efêmero:

- NF-e: Control Plane -> SecretReference -> Vault -> Signer -> Provider Router/Adapter -> Resilience -> response normalizada;
- NFC-e: fluxo equivalente com CSC provider-scoped;
- NFS-e: operação municipal/provider-specific, sem universalização artificial;
- timeout explícito, retry governado e circuit breaker particionado;
- unknown delivery outcome de autorização sem retry automático;
- restart com preservação de referências e descarte de material runtime;
- ausência de material secreto no banco e nos contracts persistíveis;
- architecture boundary e neutralidade cross-product.

## Secret / dependency / architecture audit

A suíte de fechamento valida:

- ausência de arquivos `.pfx`, `.p12`, `.pem` e `.key` no repositório;
- ausência de PEM private material em source;
- `fm_control_plane_secret_references` permanece com `reference_id`, `kind`, `tenant_id`, `unit_id`, `environment`;
- domínio não importa Vault, Gateway, Signer, Resilience, Homologation ou `cryptography`;
- packages universais não dependem de Iron Fit, Vendedor IA ou CampaIA;
- dependências produtivas limitadas a `cryptography>=44,<48` e `lxml>=5.3,<7`.

## Auditoria de diff funcional

Base V2-11 `0439246151c7edc959615361c0275961e11c3af0` -> gate B6 `b7bccf2babed336941d920eed73cd0699e6939d4`:

- 68 commits à frente;
- 0 atrás;
- 29 arquivos líquidos no gate funcional;
- 5.046 adições;
- 15 remoções;
- nenhuma migration nova;
- nenhum arquivo de `src/kordena_fiscal/domain` alterado;
- runtime novo restrito a Vault/Signer/Gateway/Resilience/Homologation e seus testes;
- CI temporário era a única alteração funcionalmente irrelevante fora desse escopo e foi restaurado após o gate.

## CI e governança

Após o gate funcional, o CI foi restaurado no commit `0e232f63d052db6ca2a7c8cd6ef5d97e3fdf0032` para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.

A documentação de fechamento será submetida a um último gate de regressão e, após esse gate, o CI será novamente restaurado para dispatch-only. Esse gate documental não autoriza merge, deploy ou promoção.

## Limites e riscos residuais

A V2-12 não declara homologação oficial externa nem comunicação produtiva concluída. Segredos/certificados/CSC/credentials reais, endpoints reais, aprovação produtiva e pilotos pertencem às etapas operacionais/homologação posteriores do Plano Mestre.

O warning de transição Node 20 -> Node 24 do GitHub Actions é de infraestrutura das actions e não afetou Ruff, Mypy ou Pytest.

## Regra de saída

A PR #13 permanece **OPEN / DRAFT / não mergeada**. V2-13 permanece **PENDENTE** e não deve ser iniciada sem autorização explícita.

**SEM MERGE. SEM DEPLOY. SEM PRODUÇÃO REAL. SEM HOMOLOGAÇÃO OFICIAL EXTERNA. SEM CUTOVER. SEM SEGREDO REAL NO REPOSITÓRIO.**
