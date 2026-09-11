# V2-01 — Identity & Namespace Policy

Status: **EM EXECUÇÃO**  
Data: 2026-09-11

## 1. Objetivo

Neutralizar a identidade Kordena no produto V2 sem introduzir regressão funcional nem realizar uma renomeação destrutiva da árvore certificada antes do congelamento dos contratos públicos.

## 2. Identidade oficial

- Produto: **FM Fiscal**
- Núcleo: **FM Fiscal Core**
- Fronteira de integração: **FM Fiscal Bridge**
- Control Plane futuro: **FM Fiscal Control Plane**
- Contratos públicos: **FM Fiscal Contracts**
- Eventos públicos: **FM Fiscal Events**
- Marca institucional: **FM Tecnologia**

Kordena é um **consumer/adapter**, não a marca-mãe do produto fiscal.

## 3. Política de namespace

O namespace Python atual `kordena_fiscal` é herdado do baseline certificado FISC-00..19. Ele permanece temporariamente por três razões:

1. preservar equivalência e rastreabilidade do baseline;
2. evitar renomeação em massa antes da estabilização dos contratos públicos do V2;
3. permitir futura migração com janela de compatibilidade, depreciação explícita e testes de regressão.

### Regra obrigatória a partir do V2-01

Nenhum novo contrato público, evento, endpoint, documento arquitetural ou componente universal deve adotar `Kordena` como identidade do produto.

Nomes novos devem usar a família `FM Fiscal` / `fm_fiscal` quando tecnicamente apropriado.

### Exceções permitidas

`Kordena` pode permanecer em:

- `kordena_fiscal` enquanto namespace legado interno/compatível;
- referências históricas ao baseline;
- `KordenaFiscalAdapter` quando o adapter privado do consumidor Kordena for criado;
- documentação de migração e cutover;
- testes que comprovem compatibilidade com o legado.

## 4. Distribuição Python

A identidade de distribuição muda no V2-01 para:

```toml
name = "fm-fiscal-core"
```

A alteração é de identidade do artefato/distribuição e não implica ainda a remoção do import path legado.

## 5. Estratégia futura de migração do import path

A migração definitiva para `fm_fiscal` deve ocorrer apenas com estratégia explícita, preferencialmente:

1. definir a superfície pública canônica;
2. introduzir `fm_fiscal` como namespace canônico;
3. manter alias/wrappers compatíveis para `kordena_fiscal` por janela determinada;
4. emitir deprecation controlada;
5. migrar consumidores internos;
6. remover o namespace legado somente após gate de compatibilidade e aprovação.

Não realizar `search/replace` global de `kordena_fiscal` no V2-01.

## 6. Invariantes arquiteturais de marca

- O Core não conhece Kordena, Iron, Vendedor IA, CampaIA ou qualquer outro produto como dependência de domínio.
- A Bridge conhece identidades de aplicações/clientes apenas por contratos, bindings e adapters.
- O branding do FM Fiscal é independente da UI de qualquer produto consumidor.
- O rodapé institucional pode mencionar **FM Tecnologia**, não Kordena como marca-mãe.
- Tokens visuais do FM Fiscal são próprios e não herdam cores do Kordena.

## 7. Gate do V2-01

V2-01 somente pode ser concluído quando:

- README apresentar FM Fiscal como produto independente;
- `pyproject.toml` usar identidade de distribuição `fm-fiscal-core`;
- Brand System oficial estiver registrado;
- design tokens oficiais estiverem registrados;
- política de namespace/compatibilidade estiver registrada;
- CI instalar a distribuição renomeada sem falha;
- Ruff PASS;
- Mypy strict PASS;
- suíte de regressão PASS;
- diff confirmar ausência de alteração semântica fiscal;
- PR Draft e evidências forem registradas no tracker.

## 8. Decisão

V2-01 neutraliza a identidade do produto agora, mas **não sacrifica a compatibilidade técnica por estética de nomenclatura**. O nome Kordena deixa de governar o produto; a retirada do namespace legado ocorre em etapa compatível e testada.
