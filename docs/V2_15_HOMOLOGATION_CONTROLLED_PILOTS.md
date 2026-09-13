# V2-15 — HOMOLOGAÇÃO + PILOTOS CONTROLADOS

Status: **EM EXECUÇÃO — B0-B3 CERTIFICADOS INTERNAMENTE / B4 AGUARDANDO NOVA AUTORIZAÇÃO**  
Branch: `v2/homologation-controlled-pilots`  
Base certificada: `v2/system-hardening` @ `15426a4460ed18c8861c807b92b98c6cfecb3126`  
Dependência: V2-14 concluída e certificada.  
Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Objetivo

Preparar e, somente quando houver evidência externa real e autorizada, executar homologação oficial e pilotos controlados do FM Fiscal Core por documento, provider e jurisdição. Antes disso, certificar que o FM Fiscal é comercialmente configurável e que o onboarding de novos clientes não exige alteração de código para diferenças fiscais já suportadas pela plataforma.

## Regra comercial superior

**Onboarding de cliente é configuração, não desenvolvimento.**

Tudo que varia apenas por host/cliente/tenant/unidade/ambiente/documento/jurisdição/município/provider/credencial/operação deve ser resolvido por configuração persistida e governada quando a capacidade correspondente já existe na plataforma.

Código novo só é admissível para evolução reutilizável do produto, como novo protocolo/provider ou nova capacidade fiscal universal. Regra fiscal/legal não pode virar campo arbitrário do cliente: deve permanecer em catálogos governados, versionados e auditáveis.

## Regras vinculantes

- mesmo source/binário deve atender clientes fiscalmente distintos por configuração;
- nenhum `if customer == ...` / `if tenant == ...` ou migration específica de cliente;
- somente `FiscalEnvironment.HOMOLOGATION` em pilotos desta fase;
- nenhum endpoint de produção, emissão produtiva ou cutover;
- segredo/certificado/CSC/credential real somente por boundaries seguros e nunca no Git;
- Control Plane persiste referências/metadados, não material secreto;
- provider/jurisdição só pode receber status de homologado com evidência externa real correspondente;
- NFS-e permanece município/provider-specific;
- readiness técnico não promove `PRODUCTION_APPROVED`;
- ausência de credencial/certificado/CSC/provider/ambiente externo deve gerar bloqueio explícito, não certificação inventada;
- tax/readiness/legal rules são catálogos governados, não configuração normativa livre do tenant;
- CI continua dispatch-only fora dos gates temporários.

## Blocos

0. **Commercial Configurability Audit + Zero-Code Customer Onboarding — CONCLUÍDO/CERTIFICADO.**
1. **Homologation Environment Readiness — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
2. **NF-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
3. **NFC-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
4. NFS-e Homologation Matrix — **PENDENTE / NÃO AUTORIZADO NESTA EXECUÇÃO**.
5. Pilotos Controlados + Go/No-Go — **PENDENTE / NÃO AUTORIZADO NESTA EXECUÇÃO**.
6. Certificação/Fechamento da fase — **PENDENTE / NÃO AUTORIZADO NESTA EXECUÇÃO**.

## B0 — Commercial Configurability + Zero-Code Onboarding — CERTIFICADO

A revisão acumulada V2-00 -> V2-15 constatou que a fundação era majoritariamente parametrizada, porém a composição comercial durável ainda possuía gaps que poderiam forçar configuração em bootstrap/runtime para clientes reais. Esses gaps foram remediados e o gate Zero-Code foi fechado.

Remediações certificadas:

1. `SecretReference` provider-scoped para CREDENTIALS/CSC no Control Plane;
2. ProviderBinding/FiscalCapabilityBinding durável por tenant/unit/environment/document/jurisdiction/operation;
3. persistência/CRUD de `FiscalProductProfile`;
4. enablement durável de documentos/operações/módulos por unidade;
5. webhook destination config;
6. workload identity/grants/config de credencial administrável;
7. homologation evidence records duráveis;
8. numbering config;
9. policy profiles governados para timeout/retry/circuit;
10. catálogos legais/readiness/tax permanecem governados e não tenant-editable.

A fronteira arquitetural foi corrigida para manter dependências concretas de provider/Vault/resilience fora do núcleo do Control Plane. O runtime comercial foi movido para `kordena_fiscal.runtime`, enquanto o Control Plane preserva somente configuração, autorização e governança.

Gate de transformação B0: SHA `0cc8eeb8ed82fd40cf9c307cf4c24873bdf11bb2`, run `34775807228`, job `103773578619`: Install PASS, Ruff PASS, Mypy PASS em **109 source files**, Pytest **592 PASS em 5.54s**. A separação arquitetural verde foi persistida em `4fbe0f962a8df0c0b44c43b6d70b8636ec965f7d`.

Gate limpo de recertificação B0: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, job `103774161682`: Install PASS, Ruff PASS, Mypy PASS em **109 source files**, Pytest **592 PASS em 8.42s**.

O gate Zero-Code cobre clientes sintéticos fiscalmente distintos usando o mesmo source/binário, persistência/restart e isolamento fail-closed entre tenant/unit/provider/environment. Nenhuma diferença fiscal já suportada exige código específico por cliente.

## B1 — Homologation Environment Readiness — CERTIFICADO INTERNAMENTE

Documento de evidência: `docs/V2_15_B1_HOMOLOGATION_ENVIRONMENT_READINESS.md`.

Foi criado um avaliador durável de readiness técnico exclusivo de `HOMOLOGATION`, com resolução exata de provider binding, provider descriptor, SecretReferences, runtime policy e homologation evidence. O serviço separa `internally_ready` de `officially_homologated`, rejeita `PRODUCTION` e falha fechado para configuração ausente ou incompatível.

Gate B1: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, job `103774775120`: Install PASS, Ruff PASS, Mypy PASS em **110 source files**, Pytest **597 PASS em 6.19s**.

## B2 — NF-e Homologation Matrix — CERTIFICADO INTERNAMENTE

Matriz: `docs/V2_15_NFE_HOMOLOGATION_MATRIX.md`.

A matriz sintética certifica `AUTHORIZE`, `QUERY` e `CANCEL` em HOMOLOGATION, resolução exata de provider/jurisdição, persistência após restart, rejeição normalizada e tratamento de entrega desconhecida sem repetir autorização cegamente.

Gate B2: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, job `103775124030`: Install PASS, Ruff PASS, Mypy PASS em **110 source files**, Pytest **601 PASS em 22.18s**.

## B3 — NFC-e Homologation Matrix — CERTIFICADO INTERNAMENTE

Matriz: `docs/V2_15_NFCE_HOMOLOGATION_MATRIX.md`.

A matriz sintética certifica `AUTHORIZE`, `QUERY` e `CANCEL` em HOMOLOGATION, CSC provider-scoped, credenciais provider-scoped, certificado por referência, ausência de fallback cross-provider e rejeição de qualquer tentativa de usar escopo `PRODUCTION`. O banco persiste somente referências opacas, nunca o material secreto.

Gate B3: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, job `103775530828`: Install PASS, Ruff PASS, Mypy PASS em **110 source files**, Pytest **605 PASS em 6.94s**. CI restaurado para `workflow_dispatch` only em `210c4f5ec2a47ce619c8eb4ca56c165454ce9d6f`.

## Estado da evidência externa

B1-B3 estão **certificados internamente** com dados sintéticos e contract tests. Nenhum provider, UF, município ou operação foi declarado oficialmente homologado porque nenhuma execução oficial externa foi realizada nesta autorização. Essa ausência não é mascarada: `external_official` permanece falso sem evidência externa real.

## Critério de fase

A V2-15 inteira **não está concluída**. B4 (NFS-e), B5 (pilotos controlados/Go-No-Go) e B6 (fechamento) permanecem pendentes e fora do limite desta autorização específica. Consequentemente a PR #16 deve permanecer aberta/Draft e não deve ser mergeada apenas porque B0-B3 estão verdes.

O trabalho interno pode ser certificado com ambientes sintéticos e contract tests. A fase somente poderá ser marcada totalmente CONCLUÍDA/CERTIFICADA quando os blocos restantes forem autorizados/executados e quando os critérios externos exigidos pelo Plano Mestre tiverem evidência real; caso contrário, o fechamento deverá registrar bloqueio externo preciso sem promover produção.
