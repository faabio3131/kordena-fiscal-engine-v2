# V2-11 — Control Plane independente

Status: **EM EXECUÇÃO — BOOTSTRAP**  
Branch: `v2/control-plane`  
Base certificada: `v2/product-contract-packs` @ `156a945cc8e2708eba21551b128ac3d673bb0cdc`  
Dependência: V2-10 concluída e certificada.

## Objetivo

Permitir operação autônoma e governada do FM Fiscal por um Control Plane independente dos produtos consumidores, sem introduzir UI comercial/premium antes do domínio operacional estar certificado e sem absorver responsabilidades de provider/vault de produção reservadas à V2-12.

## Entregas vinculantes do Plano Mestre

- onboarding de empresa e unidade;
- perfis fiscais e vigências;
- gestão de capabilities e ambientes;
- referências de certificado, CSC e credentials por abstração/referência de Vault, nunca segredo bruto;
- visão/operação governada de operações, erros, contingência, archive e reconciliação;
- RBAC administrativo;
- trilha de auditoria.

## Limites arquiteturais

- nenhum segredo, certificado PFX, CSC, token ou credential material entra no domínio, fixture ou repositório;
- V2-11 armazena e governa somente referências opacas a segredos; adapters reais de Vault/KMS são V2-12;
- Control Plane não promove sozinho `PRODUCTION_APPROVED`; Capability & Readiness permanece autoridade fiscal;
- nenhuma UI comercial/premium é construída nesta fase;
- nenhuma dependência de domínio privado de Kordena, Iron Fit, Vendedor IA ou CampaIA;
- todo escopo administrativo é explícito por tenant/unidade/ambiente e falha fechado;
- mudanças administrativas relevantes geram auditoria imutável com ator, ação, alvo, timestamp e correlation id.

## Blocos de execução

1. **Foundation administrativa:** identidade de organização/unidade fiscal, ator administrativo, RBAC, referências opacas de segredo e audit event; contratos/serviço em memória para provar invariantes antes da persistência.
2. **Persistência durável e perfis fiscais:** onboarding durável, perfis/vigências, ambientes e referências; migration explícita e restart safety.
3. **Capability/Readiness governance:** associação governada entre configuração administrativa e a Capability & Readiness API sem criar autoridade paralela.
4. **Operational Control Plane:** consultas/visões governadas de operações, erros, contingência, archive e reconciliação reutilizando os serviços certificados existentes.
5. **Certificação end-to-end:** RBAC, isolamento multi-tenant/unidade, audit trail, ausência de segredo bruto, restart/replay, diff completo e regressão integral.

## Gate da fase

A V2-11 somente será marcada `CONCLUÍDA` após todos os blocos, documentação, PR Draft, CI verde, Ruff, Mypy strict, Pytest, auditoria de diff contra V2-10, riscos residuais e restauração do CI para `workflow_dispatch`.

## Governança

PR da fase deve permanecer Draft. Nenhum merge, deploy, promoção, homologação externa ou cutover é autorizado automaticamente.
