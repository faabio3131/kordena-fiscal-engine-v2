# FM Tecnologia — Web-First SaaS Engineering Policy

Status: **REGRA ARQUITETURAL OFICIAL**  
Data: 2026-09-14  
Autoridade: Direção FM Tecnologia

## 1. Regra principal

A FM Tecnologia não deve iniciar novos SaaS como aplicação local, desktop-first ou protótipo monousuário para depois convertê-los em produto web.

Todo novo SaaS deve ser concebido desde a primeira decisão arquitetural como **web-first**, com fronteiras e contratos preparados para execução remota, autenticação, isolamento, observabilidade, deploy e operação produtiva.

Objetivo: eliminar retrabalho estrutural, duplicação de interface, migrações tardias de persistência e reescrita de runtime apenas para colocar o produto na web.

## 2. Requisitos mínimos obrigatórios desde o início

Todo novo SaaS da FM Tecnologia deve nascer com:

- frontend web responsivo ou cliente web definido como superfície principal;
- backend HTTP/API versionado e documentado;
- autenticação e autorização compatíveis com ambiente web;
- isolamento por tenant/empresa/unidade quando o domínio exigir multi-tenancy;
- banco de dados de produção compatível com concorrência e operação remota;
- migrations versionadas;
- configuração externa por ambiente;
- segredos fora do código e do repositório;
- processamento assíncrono quando necessário;
- idempotência para operações críticas;
- observabilidade: logs, métricas, tracing e health checks conforme criticidade;
- containerização/deploy reproduzível;
- separação dev/staging/produção;
- backup e restore definidos;
- responsividade desktop/tablet/mobile;
- segurança web como requisito de arquitetura, não etapa posterior;
- CI com lint, typing, testes e gates de segurança;
- documentação operacional e de integração.

## 3. Princípio de arquitetura

A interface, domínio e persistência não devem depender de execução local em uma máquina específica.

O Core de negócio deve permanecer desacoplado do transporte HTTP sempre que possível, permitindo:

`Web UI -> API -> Application/Core -> Ports -> Infrastructure`

Esse desenho evita que regras de negócio sejam reimplementadas quando uma nova superfície, integração ou cliente for adicionado.

## 4. Cloud-ready sem cloud lock-in desnecessário

Web-first não significa obrigatoriamente Kubernetes, microservices ou infraestrutura cara desde o primeiro dia.

Para V1, a FM Tecnologia pode adotar uma topologia enxuta e econômica, desde que mantenha contratos que permitam escalar depois sem reescrita do domínio.

A escolha inicial deve privilegiar:

- simplicidade operacional;
- custo controlado;
- segurança;
- portabilidade;
- observabilidade;
- automação de deploy;
- evolução incremental.

## 5. Gate obrigatório de projeto

Nenhum novo SaaS deve ser considerado arquiteturalmente pronto para implementação sem responder de forma explícita:

1. Qual é a superfície web principal?
2. Qual é o contrato HTTP/API?
3. Como usuários e sessões são autenticados?
4. Como autorização e multi-tenancy são aplicadas?
5. Qual banco será usado em produção?
6. Como migrations serão executadas?
7. Como secrets serão armazenados?
8. Como deploy e rollback funcionarão?
9. Como logs, métricas e alertas serão coletados?
10. Como backup e restore serão realizados?
11. Como ambientes dev/staging/prod serão isolados?
12. Como o produto será testado em mobile, tablet e desktop?

Ausência de resposta para esses pontos representa dívida arquitetural bloqueante antes do desenvolvimento definitivo.

## 6. Aplicação ao FM NFCORE

O FM NFCORE, originalmente construído com Core forte e portal interno, passa agora por uma fase explícita de **Web Productionization** para completar os componentes de runtime, persistência, autenticação, infraestrutura e deploy que não estavam materializados como aplicação web produtiva.

Essa etapa é corretiva para o produto atual e deve servir como referência para que novos SaaS da FM Tecnologia já nasçam web-ready.

## 7. Governança

Esta política deve ser tratada como regra padrão de System Design da FM Tecnologia para novos produtos.

Exceção somente mediante decisão arquitetural formal documentada, com justificativa explícita de por que um produto não deve ser web-first.
