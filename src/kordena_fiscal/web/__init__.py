"""FM NFCORE web runtime boundary.

The web package is an adapter layer. Fiscal business authority remains in the
application/domain services and security boundaries.
"""

from .app import (
    AuthorizedBridgeContext,
    BridgeExecutionResult,
    BridgeHttpContext,
    BridgeRequestExecutor,
    BridgeSecurityBoundary,
    create_app,
)

__all__ = [
    "AuthorizedBridgeContext",
    "BridgeExecutionResult",
    "BridgeHttpContext",
    "BridgeRequestExecutor",
    "BridgeSecurityBoundary",
    "create_app",
]
