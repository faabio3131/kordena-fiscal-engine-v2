# FM Fiscal — Brand System v1

Status: **OFICIAL — V2-01**  
Data: 2026-09-11  
Marca proprietária: **FM Tecnologia**

## 1. Princípio central

A identidade do FM Fiscal nasce do conceito **Fluxo Fiscal Contínuo**.

O produto deve comunicar simultaneamente:

- precisão técnica;
- confiança institucional;
- continuidade operacional;
- reconciliação de dados;
- automação fiscal;
- infraestrutura invisível e confiável;
- clareza para operação intensa em telas de dados.

O FM Fiscal não deve parecer um software tributário legado, nem uma extensão visual do Kordena. Sua linguagem visual é própria e independente.

## 2. Arquitetura de marca

```text
FM Tecnologia
├── FM Fiscal
├── Kordena
├── Iron
├── Vendedor IA
└── CampaIA
```

**FM Fiscal** é produto independente da FM Tecnologia. Kordena, Iron, Vendedor IA, CampaIA e futuros sistemas são consumidores/integradores do produto fiscal.

Não usar em materiais oficiais:

- `Powered by Kordena`;
- `Uma solução Kordena`;
- Kordena como marca-mãe do FM Fiscal;
- cores ou componentes herdados do Kordena como identidade principal do FM Fiscal.

Endosso institucional permitido:

- `FM Fiscal — uma tecnologia FM Tecnologia`;
- `FM Tecnologia` no rodapé institucional.

## 3. Identidade nominal

Nome oficial: **FM Fiscal**.

Aplicação tipográfica recomendada:

- `FM`: Bold/Heavy;
- `Fiscal`: Regular/Light;
- preferir construção horizontal;
- evitar caixa alta integral em textos corridos;
- não abreviar o produto publicamente como `KFE`, `Kordena Fiscal` ou nomenclaturas equivalentes.

Componentes arquiteturais oficiais:

- **FM Fiscal Core** — núcleo fiscal;
- **FM Fiscal Bridge** — fronteira de integração;
- **FM Fiscal Control Plane** — administração e operação futura;
- **FM Fiscal Contracts** — contratos públicos versionados;
- **FM Fiscal Events** — envelope/eventos públicos versionados.

## 4. Isotipo — direção de construção

O isotipo deve ser um monograma abstrato `FM`, sem símbolos fiscais literais.

Conceito geométrico:

- linhas paralelas ou vetores contínuos;
- convergência de múltiplos fluxos em uma direção comum;
- espessura uniforme;
- cantos discretamente arredondados;
- sensação de fluxo da esquerda para a direita;
- leitura secundária de camadas, reconciliação e normalização.

Metáfora arquitetural:

```text
múltiplos sistemas → normalização → núcleo fiscal único → resultado confiável
```

Evitar:

- balança;
- cifrão;
- calculadora;
- folha de papel/nota fiscal literal;
- cofre;
- escudo genérico;
- martelo jurídico;
- brasão;
- checkmark como símbolo principal.

## 5. Paleta cromática oficial

### Primárias

| Token | Nome | Hex | Uso |
|---|---|---|---|
| `brand.obsidian` | Deep Obsidian | `#0F172A` | marca, navbar, títulos, superfícies institucionais |
| `brand.cyan` | Fiscal Cyan | `#0284C7` | ação principal, links ativos, progresso e fluxo |
| `brand.canvas` | Soft Canvas | `#F8FAFC` | fundo principal da aplicação |

### Semânticas operacionais

| Token | Nome | Hex | Significado |
|---|---|---|---|
| `status.success` | Ledger Mint | `#10B981` | autorizado, conciliado, válido, conforme |
| `status.warning` | Amber Yield | `#F59E0B` | pendente, atenção, prazo ou processamento |
| `status.danger` | Fiscal Red | `#DC2626` | rejeição, erro bloqueante, divergência crítica |
| `status.info` | Fiscal Cyan | `#0284C7` | informação e processamento normal |

### Neutros

| Token | Hex | Uso |
|---|---|---|
| `neutral.50` | `#F8FAFC` | canvas |
| `neutral.100` | `#F1F5F9` | superfícies secundárias |
| `neutral.200` | `#E2E8F0` | bordas suaves |
| `neutral.500` | `#64748B` | texto secundário |
| `neutral.700` | `#334155` | tabelas, texto técnico |
| `neutral.900` | `#0F172A` | texto primário |

### Regra semântica

O verde não é a cor principal da marca. Ele é reservado prioritariamente para estados positivos e de conformidade, preservando o significado operacional dentro do produto.

## 6. Tipografia

### Marca e títulos

Preferência: **Plus Jakarta Sans**.

Uso:

- headings institucionais;
- landing pages;
- dashboards executivos;
- marca textual.

Pesos recomendados: 600, 700 e 800 para títulos; 400/500 para apoio.

### Interface

Preferência: **Inter**.

Uso:

- tabelas;
- formulários;
- filtros;
- navegação;
- relatórios;
- listas de documentos;
- valores monetários.

Para dados numéricos, ativar algarismos tabulares:

```css
font-variant-numeric: tabular-nums;
font-feature-settings: "tnum";
```

### Dados técnicos

Preferência: **Geist Mono** ou fallback monospace equivalente.

Uso restrito a:

- chaves NF-e/NFC-e;
- identificadores;
- hashes;
- correlation IDs;
- payloads/logs técnicos;
- evidências de auditoria.

## 7. Princípios de UI

A interface deve ser preparada para jornadas longas e alta densidade de informação.

Princípios obrigatórios:

- bastante respiro entre grupos, sem desperdiçar área útil de tabelas;
- valores monetários alinhados à direita;
- números tabulares;
- estados fiscais legíveis por texto + cor, nunca apenas por cor;
- prioridade à leitura de tabelas, filtros e timelines;
- contraste alto;
- hierarquia clara entre ação, status e evidência;
- dark mode futuro permitido, preservando os mesmos significados semânticos.

## 8. Personalidade verbal

Tom:

- técnico;
- preciso;
- claro;
- seguro;
- sem burocratês desnecessário;
- sem promessas absolutas de conformidade legal quando a evidência técnica não as sustenta.

Vocabulário preferido:

- `autorizado`;
- `reconciliado`;
- `validado`;
- `pendente`;
- `rejeitado`;
- `divergência`;
- `evidência`;
- `regra versionada`;
- `fonte normativa`;
- `rastreabilidade`.

## 9. Conceito de mensagem

Conceito principal: **Fluxo fiscal sem atrito.**

Mensagens de apoio permitidas:

- `Fiscal em movimento, controle em cada etapa.`
- `Documentos, regras e reconciliação em um único fluxo.`
- `Infraestrutura fiscal para produtos que não podem parar.`

O slogan comercial definitivo poderá ser refinado em V2-18; estas frases são diretrizes, não registro jurídico de marca.

## 10. Neutralização Kordena

Kordena permanece permitido apenas em:

- documentação histórica de origem;
- rastreabilidade do baseline;
- nomes de adapters específicos do consumidor Kordena;
- namespace técnico legado durante a janela de compatibilidade;
- documentos de migração/cutover.

Kordena não deve aparecer em:

- logo principal;
- favicon do FM Fiscal;
- navbar principal;
- tokens visuais;
- nomes de contratos públicos universais;
- nomenclatura do Core/Bridge/Control Plane;
- marketing do FM Fiscal como marca-mãe.

## 11. Governança da identidade

Mudanças em paleta, nome oficial, arquitetura de marca, isotipo ou tipografia-base exigem registro em ADR/Brand Decision e aprovação antes de serem consideradas oficiais.

Esta especificação é a fonte visual e nominal do V2-01 até nova decisão formal.
