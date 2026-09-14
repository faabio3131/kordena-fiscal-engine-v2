# FM Fiscal V1.0 — Sistema Visual e Padrão Comercial

Data de formalização: 2026-09-13
Status: **PADRÃO V1 APROVADO PARA IMPLEMENTAÇÃO E LANÇAMENTO COMERCIAL**

## 1. Identidade do produto

**Nome comercial:** FM Fiscal  
**Versão comercial de lançamento:** V1.0  
**Empresa:** FM Tecnologia  
**Categoria:** Fiscal Infrastructure Platform  
**Promessa de marca:** **Infraestrutura fiscal. Sob controle.**

A versão comercial V1.0 é distinta do versionamento histórico interno do repositório `kordena-fiscal-engine-v2`. O número do repositório representa evolução de engenharia; **V1.0 é a primeira versão comercial do produto FM Fiscal**.

## 2. Posicionamento

FM Fiscal não deve parecer um emissor fiscal tradicional nem um ERP contábil. A identidade deve comunicar:

1. **tecnologia avançada** — API, automação, integração e escala;
2. **segurança** — fail-closed, isolamento, secret references e authority explícita;
3. **controle** — readiness, capability, audit, archive e reconciliation;
4. **confiança empresarial** — aparência premium, sóbria e previsível.

Território visual: **Infrastructure Mission Control**.

## 3. Público principal

- SaaS e plataformas digitais;
- ERPs e software houses;
- operações multiempresa/multiunidade;
- times técnicos que precisam integrar NF-e, NFC-e e NFS-e sem duplicar regras fiscais;
- empresas que valorizam governança, rastreabilidade e segurança operacional.

## 4. Arquitetura da marca

### Lockup principal

`[símbolo Signal Ledger] FM Fiscal`

Subassinatura no produto: `Fiscal Infrastructure`.

O símbolo Signal Ledger é formado por três trilhos/documentos decrescentes e um nó luminoso. Ele representa fluxo documental, infraestrutura e controle de estado. Na interface V1 ele é construído por elementos vetoriais/CSS, sem dependência de imagem externa.

### Regra de uso

- `FM Fiscal` é sempre o nome principal;
- `FM Tecnologia` aparece como empresa, nunca competindo visualmente com o produto;
- `V1.0` pode aparecer como selo discreto;
- evitar abreviações públicas como `FMF`, `Fiscal Engine V2` ou nomes históricos do repositório.

## 5. Paleta oficial V1

### Marca

| Token | Cor | Papel |
| --- | --- | --- |
| `ink-950` | `#07101D` | fundo principal |
| `ink-900` | `#0A1628` | fundo secundário |
| `ink-850` | `#0D1B2E` | superfícies profundas |
| `surface-800` | `#10213A` | cards/painéis |
| `surface-750` | `#142943` | hover/elevated |
| `brand-primary` | `#2E6AE6` | cor principal FM Fiscal |
| `brand-bright` | `#4F8CFF` | destaque da marca |
| `brand-cyan` | `#5EE8FF` | foco, conexão, tecnologia |
| `text` | `#F4F8FF` | texto principal |
| `muted` | `#91A8BF` | texto secundário |

### Estados — não são cores de marca

| Estado | Cor | Uso exclusivo |
| --- | --- | --- |
| sucesso | `#34D399` | autorizado, saudável, concluído |
| atenção | `#FBBF24` | homologação, pendência, bloqueio recuperável |
| erro/risco | `#FB7185` | rejeição, falha, ação destrutiva |

**Regra obrigatória:** verde nunca deve ser a cor primária da marca. Marca e status fiscal precisam ser visualmente independentes.

## 6. Tipografia

### Interface

Preferência: `Inter`, com fallback para fontes nativas do sistema. Não depender de CDN pública no runtime crítico.

- H1: 30–46 px, peso 700–800, tracking negativo;
- H2: 20–36 px conforme contexto;
- corpo: 13–16 px;
- labels técnicos/eyebrows: 10–11 px, uppercase, espaçamento ampliado;
- IDs, correlation IDs e payloads: `ui-monospace` quando apresentados.

A tipografia deve comunicar precisão e tecnologia, evitando aparência de software contábil legado.

## 7. Princípios de interface

1. **Status antes de decoração.** Estado fiscal deve ser legível sem depender apenas de cor.
2. **Progressive disclosure.** Mostrar o essencial primeiro; detalhes técnicos sob demanda.
3. **Sem falso verde.** Configuração, contratação ou pagamento não equivalem a readiness fiscal.
4. **Reference-only secrets.** Nunca renderizar certificado, senha, CSC ou token real.
5. **Uma ação crítica por contexto.** Evitar múltiplos CTAs competindo.
6. **Densidade controlada.** Produto enterprise, mas sem virar planilha visual.
7. **Rastreabilidade visível.** Correlation, status e origem devem ser fáceis de localizar.
8. **Responsivo por padrão.** Desktop operacional, tablet e mobile sem perda de informação crítica.

## 8. Componentes oficiais V1

- sidebar com grupos `Operação`, `Configuração` e `Plataforma`;
- topbar com contexto e ambiente;
- CTA primário azul;
- cards de capability/metric;
- badges semânticos `success`, `warning`, `danger`, `neutral`;
- assurance strip para regras de governança;
- tabelas/listas em cards com densidade média;
- modal para ações críticas;
- empty/loading/error states;
- painel de readiness;
- painel de external gates;
- footer com produto/versão e indicação de dados sintéticos quando em referência/demo.

## 9. Linguagem e tom

Tom: **preciso, calmo, técnico e confiável**.

Usar:
- `readiness`;
- `capability`;
- `homologação`;
- `evidência`;
- `reconciliação`;
- `ambiente`;
- `escopo`;
- `referência segura`.

Evitar na superfície comercial:
- jargão interno de PR/branch;
- nomes de outros produtos da FM Tecnologia;
- `demo interna`;
- `release candidate interno`;
- promessas como `100% homologado no Brasil` sem evidência;
- linguagem exagerada do tipo `zero falhas`, `infalível` ou `IA resolve tudo`.

## 10. Pilares da V1

### EMIT
NF-e, NFC-e e NFS-e por contratos versionados.

### CONTROL
Tenant, unidade, ambiente, binding, capability e readiness governados.

### TRACE
Idempotência, correlation, audit, archive e reconciliation.

### SCALE
Bridge/API, webhooks e onboarding configurável para clientes dentro das capacidades suportadas.

## 11. Escopo visual/comercial da V1

A V1 deve ser comercializada pelo que realmente possui. CT-e, MDF-e, documentos recebidos, Fiscal Intelligence, automações no-code, white label avançado e edge/offline permanecem roadmap de V2 e não devem aparecer como funcionalidades disponíveis na V1.

## 12. Acessibilidade e qualidade

- foco de teclado sempre visível;
- skip link;
- contraste de texto e controles orientado a WCAG AA;
- estados com texto, não apenas cor;
- suporte a `prefers-reduced-motion`;
- controles com área mínima confortável;
- layout funcional em 320 px ou superior;
- nenhuma dependência visual essencial de animação.

## 13. Critérios de aceitação do padrão visual

O padrão V1 só é considerado aplicado quando:

- paleta oficial substitui a antiga identidade teal/verde;
- marca e status operacional têm cores independentes;
- nome comercial `FM Fiscal V1.0` está consistente;
- referências aos SaaS internos foram removidas da interface standalone;
- mensagens de engenharia interna foram removidas da superfície comercial;
- dados sintéticos são identificados como sintéticos;
- layout mantém acessibilidade e responsividade;
- gates críticos permanecem fail-closed na comunicação e na implementação;
- testes automatizados protegem os principais invariantes visuais/comerciais.

## 14. Limites

Este documento formaliza **identidade e experiência digital da V1**. Registro de marca, validação jurídica de textos, homologações oficiais, credenciais reais, definição final de preços e ativação produtiva permanecem processos externos e não podem ser simulados por design.
