export type FiscalEnvironment = "HOMOLOGATION" | "PRODUCTION";

export interface BridgeScope {
  hostNamespace: string;
  tenantId: string;
  unitId: string;
  environment: FiscalEnvironment;
}

export interface BridgeRequest {
  method: "POST";
  path: string;
  headers: Record<string, string>;
  body: string;
}

export interface BridgeResponse {
  status: number;
  body: string;
}

export interface BridgeTransport {
  send(request: BridgeRequest): Promise<BridgeResponse>;
}

export class FmFiscalClient {
  constructor(
    private readonly transport: BridgeTransport,
    private readonly workloadCredentialId: string,
    private readonly bearerSecret: string,
    private readonly scope: BridgeScope,
  ) {}

  capabilityQuery(body: string, correlationId: string): Promise<BridgeResponse> {
    return this.send("/v1/capabilities/query", body, correlationId);
  }

  issue(
    body: string,
    correlationId: string,
    idempotencyKey: string,
    causationId?: string,
  ): Promise<BridgeResponse> {
    return this.send("/v1/issuances", body, correlationId, idempotencyKey, causationId);
  }

  query(body: string, correlationId: string): Promise<BridgeResponse> {
    return this.send("/v1/queries", body, correlationId);
  }

  reconcile(
    body: string,
    correlationId: string,
    idempotencyKey: string,
    causationId?: string,
  ): Promise<BridgeResponse> {
    return this.send("/v1/reconciliations", body, correlationId, idempotencyKey, causationId);
  }

  private send(
    path: string,
    body: string,
    correlationId: string,
    idempotencyKey?: string,
    causationId?: string,
  ): Promise<BridgeResponse> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.bearerSecret}`,
      "X-FM-Workload-Credential-Id": this.workloadCredentialId,
      "X-FM-Host-Namespace": this.scope.hostNamespace,
      "X-FM-Tenant-Id": this.scope.tenantId,
      "X-FM-Unit-Id": this.scope.unitId,
      "X-FM-Environment": this.scope.environment,
      "X-Correlation-Id": correlationId,
      "Content-Type": "application/json",
    };
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    if (causationId) headers["X-Causation-Id"] = causationId;
    return this.transport.send({ method: "POST", path, headers, body });
  }
}

// Webhook signature verification should use the platform's constant-time HMAC-SHA256 primitive.
// The SDK deliberately does not embed provider selection, tax rules, readiness promotion, or DB access.
