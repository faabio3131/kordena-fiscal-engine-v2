# FM NFCORE — Brand Kit Oficial V1

Status: **OFICIAL — V1.0**  
Marca proprietária: **FM Tecnologia**  
Posicionamento: **Infrastructure Mission Control**

## 1. Identidade oficial

Nome comercial: **FM NFCORE**  
Tagline: **Infraestrutura fiscal. Sob controle.**

A marca deve comunicar infraestrutura crítica, precisão, confiança, escala, tecnologia e controle. O produto não deve parecer um emissor fiscal genérico, portal governamental ou software tributário legado.

## 2. Sistema de logo

O sistema oficial é formado por:

- monograma geométrico FM/NFCORE em azul elétrico e ciano;
- wordmark `FM NFCORE`, com `FM` claro e `NFCORE` em território azul/ciano;
- tagline opcional `Infraestrutura fiscal. Sob controle.`;
- versão compacta do monograma para favicon, app e espaços reduzidos.

Assets canônicos do produto:

- `portal/assets/fm-nfcore-mark.svg` — monograma;
- `portal/assets/favicon.svg` — ícone compacto.

### Regras

- não deformar, rotacionar ou adicionar efeitos não previstos;
- manter área de respiro mínima equivalente a 25% da altura do monograma;
- em fundos escuros, preservar alto contraste do azul/ciano;
- em fundos claros, usar a mesma geometria com contraste suficiente;
- não substituir o monograma por símbolos literais de nota fiscal, dinheiro, calculadora, brasão ou checkmark.

## 3. Paleta oficial

| Token | Hex | Uso |
|---|---|---|
| Obsidian | `#08121F` | fundo principal |
| Deep Navy | `#0F2747` | superfícies e estrutura |
| Electric Blue | `#2563FF` | marca, CTA e interação |
| Polar Cyan | `#00E5FF` | destaque, conectividade e foco |
| Slate | `#22344F` | elementos e bordas |
| Mist | `#E8F1FF` | superfícies claras e texto suave |
| White | `#F8FAFC` | texto de alto contraste |
| Success Green | `#22C55E` | **somente sucesso/operação** |
| Amber Signal | `#F59E0B` | atenção, homologação e warning |
| Rose/Danger | `#FB7185` | erro, rejeição e risco |

**Regra obrigatória:** verde não é cor primária da marca. É reservado a estados semânticos positivos.

A fonte de verdade machine-readable é `docs/brand/fm-nfcore.tokens.json`.

## 4. Tipografia

- Display/títulos: **Geist**, fallback Inter/system sans.
- Interface: **Inter**, fallback system sans.
- Código, IDs, logs e integrações: **JetBrains Mono** ou Geist Mono, fallback ui-monospace.

Fontes externas são recomendação de identidade; o produto deve manter fallback local funcional e não depender de download remoto para operar.

## 5. Personalidade visual

Palavras-chave obrigatórias:

- Premium
- Enterprise
- Developer-first
- Confiável
- Mission Control

A interface deve usar densidade de informação controlada, superfícies profundas, linhas finas, alto contraste, brilho ciano discreto e hierarquia rigorosa. Evitar estética de terminal genérico, excesso de neon, glassmorphism pesado ou elementos decorativos que prejudiquem leitura.

## 6. Pilares do produto

- **EMIT** — emissão fiscal governada.
- **CONTROL** — autoridade, capability e readiness explícitos.
- **TRACE** — idempotência, audit, archive e reconciliação.
- **SCALE** — integração e onboarding configurável com segurança.

## 7. Aplicações obrigatórias V1

A identidade FM NFCORE deve estar aplicada em:

- favicon e monograma do produto;
- portal/control center;
- login e onboarding quando essas superfícies forem disponibilizadas no runtime;
- documentação pública e comercial;
- landing page do produto;
- materiais Cakto;
- screenshots, vídeos, apresentações e materiais de venda.

Nenhuma peça comercial nova deve voltar a usar `FM Fiscal` como nome de produto. O nome anterior permanece permitido apenas em documentação histórica e namespaces técnicos legados onde uma renomeação causaria quebra de compatibilidade.

## 8. Segurança e linguagem comercial

A identidade premium não altera autoridade fiscal nem readiness. A interface deve continuar exibindo corretamente gates como:

- `PROD BLOQUEADA`;
- `BLOCKED_EXTERNAL`;
- `HUMAN_APPROVAL_REQUIRED`;
- referência a segredos sem expor material secreto.

Nenhum estado visual pode transformar configuração em homologação, autorização ou aprovação de produção.

## 9. Responsividade e acessibilidade

Obrigatório:

- shell adaptável para desktop, tablet e celular;
- breakpoints 1050px, 760px e 480px preservados;
- foco visível;
- skip link;
- estados descritos por texto + cor;
- suporte a `prefers-reduced-motion`;
- contraste compatível com uso prolongado em operação.

## 10. Governança

Esta especificação substitui a identidade comercial anterior do **FM Fiscal** para novas superfícies do produto. Arquivos históricos podem permanecer para rastreabilidade, mas a fonte canônica de identidade comercial da V1 passa a ser este Brand Kit e `fm-nfcore.tokens.json`.

Mudanças de nome, monograma, tagline, cores primárias ou posicionamento exigem nova decisão formal de marca.
