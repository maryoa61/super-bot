from core.models import GatewayName
from gateways.base import InvoicePayload, PaymentGateway, PaymentStatus, VerificationResult
from gateways.oxapay import OxaPayGateway
from gateways.stars import StarsGateway

# Single lookup point handlers use to go from a chosen gateway name to
# the object that actually knows how to build an invoice / verify it.
# Adding a new gateway later = write the class + add one line here.
GATEWAYS: dict[GatewayName, PaymentGateway] = {
    GatewayName.STARS: StarsGateway(),
    GatewayName.CRYPTO: OxaPayGateway(),
}

__all__ = [
    "GATEWAYS",
    "PaymentGateway",
    "InvoicePayload",
    "VerificationResult",
    "PaymentStatus",
]
