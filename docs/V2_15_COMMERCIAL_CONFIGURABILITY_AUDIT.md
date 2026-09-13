# V2-15 — COMMERCIAL CONFIGURABILITY AUDIT / ZERO-CODE CUSTOMER ONBOARDING

Status: **AUDITORIA CONCLUÍDA — REMEDIAÇÃO OBRIGATÓRIA ANTES DA HOMOLOGAÇÃO**  
Branch: `v2/homologation-controlled-pilots`  
Escopo revisado: arquitetura acumulada V2-00 -> V2-15  
Decisão arquitetural vinculante: onboarding de cliente é **configuração**, não desenvolvimento.

## 1. Regra comercial superior

O FM Fiscal é um SaaS comercial multi-tenant. Portanto, nenhuma característica que varie apenas por cliente, tenant, unidade, ambiente, documento, jurisdição, município, provider, credencial ou operação pode exigir alteração do código-fonte quando a capacidade correspondente já é suportada pela plataforma.

A regra obrigatória passa a ser:

> O mesmo binário/source do FM Fiscal deve atender clientes fiscalmente diferentes por configuração persistida e governada. Código novo só é admissível para evolução reutilizável da plataforma, como novo protocolo/provider ou nova capacidade legal universal.

Configuração não significa regra fiscal arbitrária. Normas, protocolos e capacidades legais permanecem em catálogos governados, versionados e auditáveis. Segredos permanecem fora do banco de configuração e são acessados apenas por referência segura/Vault.

## 2. Classificação usada na auditoria

- **A — CONFIGURÁVEL JÁ:** atende zero-code onboarding.
- **B — CONSTANTE DE PLATAFORMA ACEITÁVEL:** enum, protocolo, header, namespace de produto, descriptor reutilizável ou default seguro que não representa cliente específico.
- **C — CONFIG PLANE AUSENTE/INCOMPLETO:** hoje depende de composição em código, memória ou parâmetro de runtime e deveria ser administrável/durável.
- **D — CATÁLOGO GOVERNADO:** deve ser configurável pela plataforma/operador com versionamento e aprovação, mas não livremente editável pelo tenant.
- **E — SOMENTE TESTE/SINTÉTICO:** hardcode aceitável em fixtures e contract tests.

## 3. Resultado executivo

A fundação construída entre V2-00 e V2-14 **não está errada**: host namespace, tenant/unit isolation, ExecutionScope, FiscalProfile, SecretReference, adapters, provider registry, Vault, readiness, vertical modules, tax-rule engine, contract packs e persistência por partição já foram desenhados com dependency inversion e objetos de configuração.

O gap identificado é de **composição comercial durável**: várias peças estão parametrizadas, mas ainda são montadas por código/injeção de dependência ou não possuem CRUD/repositório no Control Plane. Se a V2-15 continuasse sem corrigir isso, o onboarding de clientes reais poderia exigir alteração de bootstrap/composição de runtime — o que viola a premissa comercial.

Conclusão da auditoria: **V2-15 não deve avançar para homologação/pilotos antes do gate Zero-Code Customer Onboarding.**

## 4. Achados por área

### 4.1 A — já configurável corretamente

#### Tenant, unidade e ambiente

`FiscalOrganization`, `FiscalUnitRegistration`, `ExecutionScope`, bindings e persistência já separam tenant, unidade, host e ambiente. O binding host -> conta/unidade fiscal é genérico e durável.

**Resultado:** APROVADO.

#### Perfil fiscal da unidade

`FiscalProfile` já modela CNPJ, razão social, regime tributário, inscrição estadual, CNAE, endereço, UF, município/IBGE, inscrição municipal, vigência e versão por `ExecutionScope`.

**Resultado:** APROVADO como modelo configurável e durável.

#### SecretReference + Vault boundary

Certificado, CSC e credenciais são representados por referências opacas; material secreto não pertence ao banco do Control Plane. O Vault resolve material em runtime.

**Resultado:** conceito APROVADO; existe um gap provider-scoped específico descrito em 4.2.

#### FiscalProductProfile como modelo

O domínio já possui `FiscalProductProfile` com NCM, CEST, unidade comercial/tributável, origem, GTIN, hints, vigência e versão por escopo.

**Resultado:** modelo APROVADO; falta persistência/configuração comercial durável.

#### Tax Rule Engine

`TaxRule`/`TaxRuleSelector` são versionados, effective-dated e selecionam por UF, município, regime, documento, operação, destinatário e NCM. `TaxRuleEngine` recebe regras como dados e resolve deterministicamente.

**Resultado:** arquitetura APROVADA; regras legais devem ir para catálogo governado durável, não configuração livre do cliente.

### 4.2 C — gaps de configurabilidade comercial a corrigir

#### C-01 — CRÍTICO — SecretReference não diferencia provider no Control Plane

A migration atual de `fm_control_plane_secret_references` aplica `UNIQUE (tenant_id, unit_id, environment, kind)`. O store também busca referência apenas por tenant/unit/environment/kind.

Consequência: uma unidade não consegue manter duas referências `CREDENTIALS` ou `CSC` diferentes para dois providers no mesmo ambiente, embora o runtime Vault já tenha isolamento por `provider_id`.

**Remediação obrigatória:**

- adicionar `provider_id` opcional à referência persistida;
- exigir `provider_id` para CREDENTIALS/CSC;
- manter CERTIFICATE provider-independent salvo necessidade futura específica;
- unicidade provider-scoped para CREDENTIALS/CSC;
- migration backward-safe;
- sem material secreto no banco.

#### C-02 — ALTO — provider binding/selection ainda não é durável por cliente

`ProviderDescriptor`, `ConfiguredProviderAdapter` e `ProviderRegistry` são reutilizáveis, mas adapters/descriptors são compostos em runtime. Não existe no Control Plane uma ligação durável do tipo:

`tenant/unit/environment/document/jurisdiction/operation -> provider_id`.

Consequência: trocar/selecionar provider por cliente pode depender da composição do processo.

**Remediação obrigatória:** criar `ProviderBinding`/`FiscalCapabilityBinding` durável e administrável, referenciando somente providers presentes em catálogo governado.

#### C-03 — ALTO — catálogo fiscal de produtos/serviços não possui persistence/config CRUD no Control Plane

`FiscalProductProfile` existe no domínio, mas não há repository/store correspondente no UoW/Control Plane atual.

Consequência: classificação NCM/CEST/unidades/origem/GTIN/hints pode acabar sendo fornecida por código ou por request do SaaS host sem autoridade durável central.

**Remediação obrigatória:** repository/control-plane service para perfis fiscais de produto/serviço versionados e effective-dated por tenant/unidade.

#### C-04 — ALTO — destinos de webhook são abstraídos, porém não há configuração durável

Existe `WebhookDestinationResolver`, mas nenhum cadastro durável de destino por host/tenant/unit/evento foi identificado.

Consequência: endpoint de callback de um novo cliente/host pode depender de resolver implementado/configurado fora do Control Plane.

**Remediação obrigatória:** `WebhookDestinationConfig` durável, HTTPS-only, sem credentials na URL, auditável, com allowlist/política de segurança.

#### C-05 — ALTO — workload identities/grants ainda são compostos em memória

`CallerIdentity`, `HostScopeGrant`, `WorkloadCredentialRecord` e `WorkloadAuthenticator` são data-driven, mas o authenticator recebe tupla de records em memória; `S2SAuthorizer` recebe registry de bindings em memória.

Consequência: onboarding/rotação/revogação de integração S2S pode exigir reconfiguração de processo ou código de bootstrap.

**Remediação obrigatória:** store/resolver durável para identidade, grants, status/revogação e metadata de credencial; segredo/token continua fora do banco ou somente hash seguro conforme contrato. Autorizer deve depender de resolver/port durável, não registry concreto em memória.

#### C-06 — ALTO — homologation matrix/evidence não é durável por tenant/unidade

`TechnicalHomologationMatrix` recebe regras em memória. A semântica é correta, porém não existe registro administrável de evidência/status por tenant/unit/provider/document/jurisdiction/environment/operation.

**Remediação obrigatória:** `HomologationEvidenceRecord`/gate state durável e auditável. Evidência oficial externa continua obrigatória para marcar homologado.

#### C-07 — ALTO — documentos/operações/módulos habilitados por unidade não possuem binding comercial explícito

Vertical modules e contract packs são extensíveis, mas não existe assignment durável por unidade para dizer quais documentos, operações e módulos estão habilitados para aquele cliente.

**Remediação obrigatória:** `FiscalCapabilityBinding`/`VerticalModuleAssignment` effective-dated por tenant/unit/environment, sempre subordinado ao catálogo/capability central.

#### C-08 — MÉDIO — série e política de numeração são parametrizadas, mas não administradas duravelmente

`FiscalSequenceKey` recebe série e `FiscalSequencePolicy` é explicitamente host-configured, porém não existe configuração administrativa persistida para série/first/max por tenant/unit/environment/model.

**Remediação:** `NumberingConfiguration` governada antes de produção.

#### C-09 — MÉDIO — retry/timeout/circuit/rate-limit são configuráveis por construtor, não por policy profile durável

Os valores já são data objects e possuem limites seguros, mas são injetados em runtime.

**Remediação:** catálogos de policy profiles com bounds definidos pela plataforma; tenant/provider pode selecionar somente perfis permitidos. Não expor knobs inseguros arbitrários.

#### C-10 — MÉDIO — composição operacional do outbox é deployment-config, não configuração comercial explícita

`limit`, lease e retry possuem defaults em código.

**Remediação:** tratar como configuração operacional da implantação/plataforma, não por cliente, com defaults seguros. Não é bloqueio de onboarding se for externalizada no runtime/deployment config.

### 4.3 D — catálogos governados, não tenant-editable

#### D-01 — Jurisdiction Capability / Readiness rules

São data-driven e versionadas, mas atualmente montadas em memória. Devem futuramente ser carregadas de catálogo regulatório governado/versionado. Cliente não pode promover readiness ou editar regra legal livremente.

#### D-02 — Tax rules

Tax rules devem ser versionadas, effective-dated, auditadas e publicadas pela autoridade administrativa da plataforma. Cliente seleciona/fornece fatos fiscais; não edita CFOP/CST/regra normativa arbitrariamente.

#### D-03 — Restaurant/legal vertical rules

Percentuais e limites legais atualmente codificados no módulo de restaurante são regras normativas de plataforma, não preferência do cliente. Devem migrar para rule packs governados/versionados quando necessário para evolução regulatória, sem virar campo livre do tenant.

#### D-04 — Provider catalog

Um novo protocolo/provider desconhecido pode exigir um adapter reutilizável uma única vez. Depois de homologado na plataforma, clientes apenas selecionam/configuram o provider pelo Control Plane.

### 4.4 B — constantes aceitáveis

Não são defeitos de configurabilidade:

- enums fiscais/protocolos;
- nomes de headers;
- regras estruturais de XML;
- namespaces fixos dos produtos FM (`fm.kordena`, etc.) enquanto representarem identidade da integração, não cliente;
- descriptors de módulos/capabilities disponíveis;
- catálogo de contract packs dos produtos FM;
- defaults seguros de plataforma, desde que exista caminho de configuração quando a variação comercial exigir.

Contract packs devem funcionar como catálogo de capacidades suportadas/defaults do produto, nunca como autoridade fiscal fixa de todos os clientes daquele SaaS.

### 4.5 E — hardcodes de testes

Tenants, unidades, providers, certificados sintéticos, CSC sintético, municípios e payloads em fixtures/testes são aceitáveis desde que não sejam usados como configuração produtiva.

## 5. Arquitetura alvo — Commercial Fiscal Configuration Plane

O Control Plane deve evoluir para resolver a composição abaixo sem mudança de código:

`Host -> Tenant -> Unit -> Environment -> Fiscal Profile -> Enabled Capabilities/Documents -> Jurisdiction -> Provider Binding -> Secret References -> Policy Profiles -> Homologation State`

Entidades prioritárias:

1. `ProviderCatalogEntry` — governado pela plataforma.
2. `ProviderBinding` / `FiscalCapabilityBinding` — tenant/unit/env/document/jurisdiction/operation -> provider.
3. `SecretReference.provider_id` para CREDENTIALS/CSC.
4. `FiscalProductProfile` repository + CRUD administrativo.
5. `WebhookDestinationConfig`.
6. `WorkloadIdentityConfig` + grants/revocation/credential metadata.
7. `HomologationEvidenceRecord`.
8. `VerticalModuleAssignment` / document-operation enablement.
9. `NumberingConfiguration`.
10. `RuntimePolicyProfile` para timeout/retry/circuit/rate-limit com bounds governados.
11. Governed catalogs para `TaxRule` e jurisdiction readiness.

Todos os objetos administrativos devem possuir isolamento por tenant/unidade/ambiente quando aplicável, versionamento/effective dating onde necessário e audit trail para mutações relevantes.

## 6. Gate obrigatório — Zero-Code Customer Onboarding

Antes de retomar homologação oficial/pilotos da V2-15, deve existir teste automatizado que configure, persista, reinicie o runtime e opere três clientes sintéticos distintos sem alterar source entre eles:

### Cliente A — restaurante / SP

- host: produto FM compatível;
- NF-e + NFC-e;
- provider A;
- certificado/credentials/CSC por referências;
- módulo restaurante selecionado;
- configuração fiscal própria.

### Cliente B — academia/serviços / município de SP

- host diferente ou tenant distinto;
- NFS-e municipal;
- provider B;
- credenciais próprias;
- módulo fitness/service;
- configuração fiscal própria.

### Cliente C — varejo / MG

- NF-e + NFC-e;
- provider C;
- referências próprias;
- perfil e catálogo fiscal próprios.

### Critérios de aprovação

- mesmo código/binário para os três clientes;
- toda diferença nasce de dados/configuração persistida;
- restart mantém configuração;
- provider correto é resolvido por configuração;
- SecretReference correta é selecionada sem fallback cross-provider;
- documentos/operações são habilitados por configuração;
- nenhuma configuração de A aparece para B/C;
- nenhum `if tenant ==`, `if customer ==` ou migration específica de cliente;
- nenhuma regra legal arbitrária é editável pelo tenant;
- nenhuma credencial real entra no banco/Git/log;
- tentativa cross-tenant/cross-unit/cross-provider/cross-environment falha fechado.

## 7. Ordem de remediação obrigatória

### R1 — Configuração comercial mínima bloqueante

1. corrigir SecretReference provider-scoped;
2. criar ProviderBinding/FiscalCapabilityBinding durável;
3. criar FiscalProductProfile durável;
4. criar enablement de documento/operação/módulo por unidade;
5. implementar Zero-Code Customer Onboarding E2E.

### R2 — Integração comercial/operacional

6. webhook destination config;
7. workload identity/grants durable config;
8. homologation evidence records;
9. numbering configuration;
10. policy profiles governados.

### R3 — governança de catálogo

11. externalizar/carregar tax/readiness/legal rule packs por catálogo governado versionado, sem dar poder normativo arbitrário ao tenant.

## 8. Decisão para V2-15

A V2-15 fica em **EM EXECUÇÃO — REMEDIAÇÃO DE CONFIGURABILIDADE COMERCIAL**.

O B1 original de homologation environment readiness não é cancelado; ele fica subordinado a um novo gate anterior:

**B0 — Commercial Configurability Audit + Zero-Code Onboarding.**

A auditoria B0 está concluída. A remediação e o teste Zero-Code ainda precisam ficar verdes antes de avançar para homologação externa/pilotos.

## 9. Não regressão

Esta correção de rota não autoriza:

- segredo real no repositório;
- endpoint produtivo;
- produção real;
- merge;
- deploy;
- cutover;
- readiness autopromovido;
- homologação fictícia;
- regra fiscal livremente editável pelo cliente.

## 10. Resultado

**AUDITORIA: CONCLUÍDA.**  
**FUNDAÇÃO: REUTILIZÁVEL E MAJORITARIAMENTE PARAMETRIZADA.**  
**GAP: COMPOSIÇÃO/CONFIGURAÇÃO COMERCIAL DURÁVEL INCOMPLETA.**  
**AÇÃO: REMEDIAR NA V2-15 ANTES DE HOMOLOGAÇÃO/PILOTOS.**  
**CRITÉRIO DE SAÍDA: ZERO-CODE CUSTOMER ONBOARDING CERTIFICADO.**
