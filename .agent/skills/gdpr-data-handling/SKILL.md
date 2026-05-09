---
type: feature
name: gdpr-data-handling
description: "Master GDPR-compliant data processing with consent management, data subject rights, privacy-by-design architecture, and encryption. Covers legal bases (consent, contract, legitimate interest), data retention policies, right to erasure ('right to be forgotten'), data portability, breach notification, DPA/TPA management, pseudonymization, encryption at rest/transit, access controls, audit logging, and DSR (Data Subject Request) workflows. Includes patterns for consent UI, cookie management, data inventory, impact assessments (DPIA), incident response, and compliance monitoring. Use when processing EU personal data, implementing privacy controls, designing privacy-first systems, handling data subject requests, or conducting GDPR compliance audits."
---

# GDPR-Compliant Data Processing & Privacy

Master implementing privacy by design with data subject rights, consent management, and regulatory compliance.

---

## GDPR Core Principles

| Principle | Requirement | Implementation |
|-----------|-------------|-----------------|
| **Lawfulness** | Legal basis for processing | Consent, contract, legitimate interest, legal obligation |
| **Purpose Limitation** | Use data only for stated purpose | Document processing purpose in privacy policy |
| **Data Minimization** | Collect only necessary data | Review data collection before each endpoint |
| **Accuracy** | Keep data accurate & up-to-date | Provide user update capabilities |
| **Storage Limitation** | Delete after retention period | Schedule automated deletion |
| **Integrity & Confidentiality** | Encrypt, access control | TLS, encryption at rest, RBAC |
| **Accountability** | Demonstrate compliance | Document everything, audit trails |
| **Transparency** | Clear privacy communications | Privacy policy, consent forms |

---

## Pattern 1: Legal Basis & Consent Management

### Consent-Based Processing

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

class ConsentType(Enum):
    """Types of GDPR-compliant consent."""
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    THIRD_PARTY_SHARING = "third_party"
    PROFILING = "profiling"
    COOKIES = "cookies"

@dataclass
class Consent:
    """Recorded consent for data processing."""
    user_id: str
    consent_type: ConsentType
    granted: bool           # True = given, False = withdrawn
    timestamp: datetime     # When consent was given/withdrawn
    ip_address: str        # IP at time of consent
    user_agent: str        # Browser/device info
    version: int           # Privacy policy version consented to
    method: str            # "email", "website_form", "api"

class ConsentManager:
    """Manage user consents."""

    def __init__(self, db):
        self.db = db

    async def record_consent(self, consent: Consent) -> bool:
        """Record user consent with full audit trail."""
        # Store in immutable audit log
        self.db.audit_log.insert({
            "event": "CONSENT_RECORDED",
            "user_id": consent.user_id,
            "consent_type": consent.consent_type.value,
            "granted": consent.granted,
            "timestamp": consent.timestamp.isoformat(),
            "ip_address": consent.ip_address,
            "user_agent": consent.user_agent,
        })

        # Store current consent state
        self.db.consents.update_one(
            {"user_id": consent.user_id, "type": consent.consent_type.value},
            {
                "$set": {
                    "granted": consent.granted,
                    "timestamp": consent.timestamp,
                    "version": consent.version,
                }
            },
            upsert=True
        )

        return True

    async def has_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Check if user has given consent."""
        consent = self.db.consents.find_one({
            "user_id": user_id,
            "type": consent_type.value,
            "granted": True
        })
        return consent is not None

    async def withdraw_consent(self, user_id: str, consent_type: ConsentType):
        """User withdraws consent (right to withdraw)."""
        await self.record_consent(Consent(
            user_id=user_id,
            consent_type=consent_type,
            granted=False,
            timestamp=datetime.utcnow(),
            ip_address="system",
            user_agent="withdraw_request",
            version=1,
            method="api"
        ))

# Consent UI with explicit opt-in (not pre-checked)
@app.post("/consent")
async def update_consent(
    user_id: str,
    consent_data: dict,
    request: Request,
    manager: Annotated[ConsentManager, Depends()],
):
    """Record user consent choices."""
    for consent_type, granted in consent_data.items():
        consent = Consent(
            user_id=user_id,
            consent_type=ConsentType[consent_type.upper()],
            granted=granted,
            timestamp=datetime.utcnow(),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            version=1,
            method="website_form"
        )
        await manager.record_consent(consent)

    return {"status": "consent_recorded"}
```

---

## Pattern 2: Data Subject Rights (DSR) Fulfillment

### Right to Access, Erasure, Portability

```python
class DataSubjectRights:
    """Fulfill GDPR data subject rights."""

    def __init__(self, db):
        self.db = db

    async def right_to_access(self, user_id: str) -> dict:
        """Right to receive copy of personal data (within 30 days)."""
        # Collect all user data
        user_profile = self.db.users.find_one({"_id": user_id})
        orders = list(self.db.orders.find({"user_id": user_id}))
        interactions = list(self.db.interactions.find({"user_id": user_id}))
        preferences = self.db.preferences.find_one({"user_id": user_id})

        return {
            "user_profile": user_profile,
            "orders": orders,
            "interactions": interactions,
            "preferences": preferences,
            "exported_at": datetime.utcnow().isoformat(),
            "format": "json"  # GDPR requires machine-readable format
        }

    async def right_to_erasure(self, user_id: str):
        """Right to be forgotten (with exceptions)."""
        # Check for legal holds/exceptions
        exceptions = [
            "ongoing_legal_proceedings",
            "contract_fulfillment",
            "audit_obligations",
        ]

        # Identify what can be deleted
        can_delete = {
            "preferences": True,      # Deletable
            "interaction_history": True,
            "consent_records": False, # Keep for audit trail
            "orders": False,          # Legal obligation (tax)
        }

        # Anonymize or delete data
        self.db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "email": f"deleted_{user_id}@deleted.local",
                    "name": "Deleted User",
                    "phone": None,
                    "address": None,
                    "deleted_at": datetime.utcnow(),
                }
            }
        )

        # Delete deletable data
        if can_delete["interaction_history"]:
            self.db.interactions.delete_many({"user_id": user_id})

        return {"status": "erasure_complete", "exceptions": exceptions}

    async def right_to_portability(self, user_id: str) -> bytes:
        """Right to receive data in portable format."""
        data = await self.right_to_access(user_id)

        # Generate JSON export
        export = json.dumps(data, indent=2, default=str)

        # Could also generate CSV, XML, etc.
        return export.encode("utf-8")

    async def right_to_rectification(self, user_id: str, corrections: dict):
        """Right to correct inaccurate data."""
        # Validate corrections
        allowed_fields = ["name", "email", "address", "phone"]
        corrections = {k: v for k, v in corrections.items() if k in allowed_fields}

        # Update with audit trail
        self.db.audit_log.insert({
            "event": "DATA_RECTIFICATION",
            "user_id": user_id,
            "corrections": corrections,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.db.users.update_one(
            {"_id": user_id},
            {"$set": corrections}
        )

        return {"status": "data_rectified"}
```

---

## Pattern 3: Data Retention & Scheduled Deletion

### Lifecycle Management

```python
from datetime import datetime, timedelta
import schedule
import asyncio

class DataRetentionPolicy:
    """Enforce data retention limits."""

    RETENTION_PERIODS = {
        "user_profile": timedelta(days=365*3),  # 3 years after account closure
        "transaction_logs": timedelta(days=2555),  # 7 years (legal requirement)
        "analytics_logs": timedelta(days=90),
        "marketing_emails": timedelta(days=365),  # 1 year
        "cookies": timedelta(days=365),
    }

    def __init__(self, db):
        self.db = db

    async def auto_delete_expired_data(self):
        """Scheduled job to delete expired data."""
        now = datetime.utcnow()

        # Delete expired analytics
        self.db.analytics_logs.delete_many({
            "created_at": {"$lt": now - self.RETENTION_PERIODS["analytics_logs"]}
        })

        # Delete expired cookies
        self.db.cookies.delete_many({
            "created_at": {"$lt": now - self.RETENTION_PERIODS["cookies"]}
        })

        # Archive old transaction logs (for audit)
        old_transactions = self.db.transactions.find({
            "created_at": {"$lt": now - self.RETENTION_PERIODS["transaction_logs"]}
        })

        if old_transactions:
            self.db.archived_transactions.insert_many(old_transactions)
            self.db.transactions.delete_many({
                "created_at": {"$lt": now - self.RETENTION_PERIODS["transaction_logs"]}
            })

        return {"deleted_records": "completed"}

# Schedule deletion (e.g., daily at 2 AM)
schedule.every().day.at("02:00").do(auto_delete_expired_data)

async def run_scheduler():
    """Background task for scheduled deletions."""
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)
```

---

## Pattern 4: Encryption & Data Protection

### Securing Personal Data

```python
from cryptography.fernet import Fernet
import os

class DataEncryption:
    """Encrypt sensitive personal data."""

    def __init__(self):
        # Key management (use KMS in production)
        self.key = os.getenv("ENCRYPTION_KEY").encode()
        self.cipher = Fernet(self.key)

    def encrypt_pii(self, data: str) -> str:
        """Encrypt Personally Identifiable Information."""
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode()

    def decrypt_pii(self, encrypted_data: str) -> str:
        """Decrypt PII (only when needed)."""
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return decrypted.decode()

class PersonalDataModel:
    """Store encrypted sensitive fields."""

    def __init__(self, db, encryption: DataEncryption):
        self.db = db
        self.encryption = encryption

    async def create_user(self, user_data: dict):
        """Create user with encrypted PII."""
        # Encrypt sensitive fields before storage
        user_data["email"] = self.encryption.encrypt_pii(user_data["email"])
        user_data["phone"] = self.encryption.encrypt_pii(user_data["phone"])

        self.db.users.insert_one(user_data)

    async def get_user_email(self, user_id: str) -> str:
        """Retrieve and decrypt email only when needed."""
        user = self.db.users.find_one({"_id": user_id})
        return self.encryption.decrypt_pii(user["email"])

# TLS for transit
# Configure in FastAPI:
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*.example.com"]
)

# All responses HTTPS-only
@app.middleware("http")
async def https_redirect(request, call_next):
    if request.url.scheme == "http" and not request.url.hostname.startswith("localhost"):
        return RedirectResponse(
            url=request.url.replace(scheme="https"),
            status_code=301
        )
    return await call_next(request)
```

---

## Pattern 5: Audit Logging & Compliance Monitoring

### Immutable Audit Trail

```python
class AuditLog:
    """Immutable log for compliance monitoring."""

    def __init__(self, db):
        self.db = db

    async def log_access(self, user_id: str, resource: str, action: str, actor_id: str):
        """Log data access for audit trail."""
        self.db.audit_logs.insert_one({
            "timestamp": datetime.utcnow(),
            "event_type": "DATA_ACCESS",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "actor_id": actor_id,
            "ip_address": request.client.host,
        })

    async def log_breach(self, description: str, affected_users: int):
        """Log data breach for 72-hour notification requirement."""
        self.db.breach_log.insert_one({
            "timestamp": datetime.utcnow(),
            "description": description,
            "affected_users": affected_users,
            "notification_deadline": datetime.utcnow() + timedelta(hours=72),
            "status": "reported_to_dpa",
        })

# Monitoring queries
async def check_compliance_status():
    """Generate GDPR compliance report."""
    return {
        "data_retention_violations": await check_retention(),
        "missing_consents": await check_consent_coverage(),
        "unresolved_dsr": await check_pending_requests(),
        "recent_breaches": await check_breach_status(),
    }
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Document legal basis** | Required by GDPR | Create Data Processing Agreement (DPA) |
| **Explicit opt-in consent** | "Consent" is not pre-checked | Clear, granular checkboxes |
| **Retention deadlines** | Storage limitation principle | Auto-delete after retention period |
| **Audit everything** | Accountability principle | Immutable logs of all data access |
| **Encrypt PII** | Integrity & confidentiality | At rest & in transit (TLS + encryption) |
| **Respond to DSRs in 30 days** | Legal requirement | Track request deadline |
| **Privacy by design** | Mandatory | Collect minimal data, encrypt by default |
| **DPA with processors** | Legal requirement | Document processor obligations |

---

## Implementation Checklist

- [ ] Create privacy policy & data processing addendum
- [ ] Map all personal data flows (Data Inventory)
- [ ] Document legal basis for each processing activity
- [ ] Implement consent management (record, track, withdraw)
- [ ] Set retention periods & auto-deletion
- [ ] Encrypt PII at rest and in transit
- [ ] Implement DSR fulfillment (access, erasure, portability)
- [ ] Create immutable audit log
- [ ] Set up breach notification process (72 hours)
- [ ] Perform DPIA (Data Protection Impact Assessment)
- [ ] Regular compliance monitoring & reporting
- [ ] Train team on GDPR requirements
