# NFCore — piloto com escritório contábil (04/11/2026)

## CURRENT certificado

Main 71c5adc; production/deployed afc2d6d; CI produção #41844986296 SUCCESS. Web pilot preflight PASS. Runtime /runtime/profile: único handler fiscal queryArchiveReference; fiscal_provider_transport_real_configured=false; fiscal_external_secret_client_configured=false; fiscal_signer_configured=false; fiscal_runtime_external_execution_ready=false; fiscal_production_activated=false; fiscal_production_active_grants=0. Assim, emissão oficial de clientes não está habilitada.

## Separação de identidade

FM Tecnologia é fornecedora do SaaS. Escritório contábil e seus clientes são os emitentes. Certificado, CNPJ, UF, município e autorização de cada empresa precisam de configuração e isolamento próprios por tenant/unidade/ambiente. Não usar o certificado da FM Tecnologia.

## Autoridades já existentes a reutilizar

FiscalApplicationService, CanonicalFiscalOperationPath, build_provider_operation_handlers, PKCS#12 cryptography_adapter, assinatura, vault, idempotência, recuperação, motor tributário, RBAC e PostgreSQL. Não criar API/engine/vault paralelos.

## Pendências internas reais (CURRENT → TARGET)

1. Cadastro governado por CNPJ/tenant/unidade de certificado A1/PKCS#12 (senha não logável), validação de emissor e expiração, armazenamento em vault, rotação/revogação e trilha RBAC/step-up. A3 requer fluxo próprio.
2. Adapters oficiais concretos de NF-e/NFC-e por UF/ambiente, CSC NFC-e quando exigível; certificados e assinatura, protocolo, recibo, consulta, cancelamento e inutilização; selecionar endpoint e leiaute oficial com prova.
3. Adapter de NFS-e nacional ou municipal por cidade/provedor, autenticação/assinatura, autorização, consulta e cancelamento disponíveis.
4. Compor handlers fiscais reais na API por escopo, sem trocar o motor ou aceitar headers/UI como autoridade. Bloquear quando provider/cert/tenant faltarem.
5. E2E autenticado por empresa e integração com PostgreSQL, isolamento de tenant e secret, idempotência e reconciliação de timeout. CI SHA exato + staging + homologação oficial por operação.
6. Ativação fiscal real exige evidência da jurisdição, autorização do emissor, testes homologados e Go/No-Go humano. Jamais deduzir isso de health HTTP.

## Gates auditáveis

scripts/pilot_contabo_preflight.py --require-web certifica somente Web sem autenticação real.
--require-accountant-configuration exige transporte oficial, vault, assinador e handlers principais; mesmo PASS não homologa empresa nem permite emissão.
--require-fiscal-provider conserva contrato anterior.

Estado: INTERNAL_FISCAL_INTEGRATION_INCOMPLETE. O contador pode analisar e validar dados controlados; não emitir oficialmente sem gates externos e configurações internas acima.
