---
name: api-security-fuzzer
description: "Master API security testing with fuzzing, injection testing, authentication bypass, and data exposure detection. Covers OWASP Top 10 (injection, broken auth, data exposure), fuzzing strategies, payload generation, automated vulnerability scanning, and remediation patterns. Includes SQLi detection, XSS fuzzing, broken authentication, CORS bypasses, rate limit testing, input validation fuzzing, and error response analysis. Use when building secure APIs, testing endpoints before deployment, preventing OWASP vulnerabilities, implementing security gates, or discovering edge cases in authentication/authorization logic."
type: feature
---

# API Security Fuzzing & Vulnerability Detection

Master API security testing with fuzzing, injection detection, authentication bypass discovery, and data exposure prevention.

---

## Core Concepts

### Threat Model for API Security

| Threat | OWASP Category | Detection Method | Severity |
|--------|----------------|------------------|----------|
| SQL Injection | Injection | SQLi payload fuzzing | **Critical** |
| XSS in responses | Injection | XSS payload analysis | **High** |
| Broken Auth/Session Fixation | Broken Auth | Auth bypass attempts | **Critical** |
| CORS Misconfiguration | Broken CORS | Cross-origin requests | **High** |
| Data Exposure (PII) | Sensitive Data | Response scanning | **High** |
| Rate Limit Bypass | DoS | Burst testing | **Medium** |
| Path Traversal | Injection | Directory traversal payloads | **High** |
| Logic Bypasses (negative balance) | Logic Flaws | State transition testing | **Medium** |

---

## Pattern 1: Payload Injection Fuzzing

### SQLi Detection

```python
from typing import list
import httpx
import asyncio

class SQLiDetector:
    """Detect SQL injection vulnerabilities in APIs."""

    SQLI_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE users;--",
        "1' UNION SELECT NULL, NULL, NULL--",
        "admin' --",
        "1' AND SLEEP(5)--",  # Time-based detection
    ]

    ERROR_PATTERNS = [
        r"SQL syntax",
        r"MySQL.*error",
        r"PostgreSQL.*error",
        r"Syntax error",
        r"ORA-\d{5}",
    ]

    async def fuzz_endpoint(self, url: str, param: str) -> dict:
        """Test parameter for SQLi vulnerabilities."""
        async with httpx.AsyncClient(timeout=10) as client:
            vulnerabilities = []

            for payload in self.SQLI_PAYLOADS:
                params = {param: payload}

                try:
                    response = await client.get(url, params=params)

                    # Check for SQL error signatures
                    if any(
                        pattern in response.text
                        for pattern in self.ERROR_PATTERNS
                    ):
                        vulnerabilities.append({
                            "type": "SQL Injection",
                            "param": param,
                            "payload": payload,
                            "status": response.status_code,
                            "evidence": response.text[:500],
                        })
                except httpx.TimeoutException:
                    vulnerabilities.append({
                        "type": "SQL Injection (Time-based)",
                        "param": param,
                        "payload": payload,
                        "evidence": "Request timed out (SLEEP detected)",
                    })

            return {"endpoint": url, "vulnerabilities": vulnerabilities}
```

### XSS Payload Fuzzing

```python
class XSSDetector:
    """Detect XSS vulnerabilities in API responses."""

    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<iframe src='javascript:alert(1)'></iframe>",
    ]

    async def detect_xss(self, url: str, param: str) -> list:
        """Detect XSS by checking if payload is reflected unescaped."""
        async with httpx.AsyncClient() as client:
            xss_findings = []

            for payload in self.XSS_PAYLOADS:
                params = {param: payload}
                response = await client.get(url, params=params)

                if payload in response.text:  # Reflected without escaping
                    xss_findings.append({
                        "type": "Reflected XSS",
                        "param": param,
                        "payload": payload,
                        "severity": "High",
                    })

            return xss_findings
```

---

## Pattern 2: Authentication Bypass Detection

### Session Fixation & Weak Auth

```python
class AuthBypassDetector:
    """Detect authentication weaknesses and bypass possibilities."""

    async def test_session_fixation(self, base_url: str) -> dict:
        """Test if session ID from one user works for another."""
        async with httpx.AsyncClient() as client:
            # Get session 1
            login1 = await client.post(
                f"{base_url}/login",
                json={"username": "user1", "password": "pass1"}
            )
            session1 = login1.cookies.get("session_id")

            # Get session 2
            login2 = await client.post(
                f"{base_url}/login",
                json={"username": "user2", "password": "pass2"}
            )
            session2 = login2.cookies.get("session_id")

            # Cross-use sessions
            client.cookies.set("session_id", session1)
            resp = await client.get(f"{base_url}/profile")

            if "user2" not in resp.text:  # Session 1 should not give user2 profile
                return {"vulnerability": "Session Fixation", "severity": "Critical"}

            return {"status": "secure"}

    async def test_auth_header_bypass(self, url: str) -> dict:
        """Test if API can be accessed without auth headers."""
        async with httpx.AsyncClient() as client:
            # Without auth
            resp_no_auth = await client.get(url)

            # With invalid auth
            resp_invalid = await client.get(
                url,
                headers={"Authorization": "Bearer invalid_token"}
            )

            if resp_no_auth.status_code == 200:
                return {
                    "vulnerability": "Missing Authentication",
                    "severity": "Critical",
                }

            if resp_invalid.status_code == 200:
                return {
                    "vulnerability": "Broken Auth Validation",
                    "severity": "High",
                }

            return {"status": "secure"}
```

---

## Pattern 3: Data Exposure Scanning

### Sensitive Data Detection in Responses

```python
import re
from dataclasses import dataclass

@dataclass
class SensitivePattern:
    """Pattern for detecting sensitive data."""
    name: str
    pattern: str
    severity: str

class DataExposureDetector:
    """Scan API responses for exposed sensitive data."""

    SENSITIVE_PATTERNS = [
        SensitivePattern(
            name="Credit Card",
            pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            severity="Critical",
        ),
        SensitivePattern(
            name="Social Security Number",
            pattern=r"\b\d{3}-\d{2}-\d{4}\b",
            severity="Critical",
        ),
        SensitivePattern(
            name="API Key",
            pattern=r"api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{20,}",
            severity="Critical",
        ),
        SensitivePattern(
            name="Email",
            pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            severity="Medium",
        ),
        SensitivePattern(
            name="Password Hash",
            pattern=r"password['\"]?\s*[:=]\s*['\"]?[a-f0-9]{32,}",
            severity="High",
        ),
    ]

    def scan_response(self, response_text: str) -> list:
        """Scan response for sensitive data exposure."""
        findings = []

        for pattern in self.SENSITIVE_PATTERNS:
            matches = re.finditer(pattern.pattern, response_text, re.IGNORECASE)

            for match in matches:
                findings.append({
                    "type": pattern.name,
                    "value": match.group(0)[:50],  # Truncate for safety
                    "severity": pattern.severity,
                })

        return findings
```

---

## Pattern 4: CORS & Preflight Bypass

```python
class CORSDetector:
    """Detect CORS misconfigurations."""

    async def test_cors_headers(self, url: str) -> dict:
        """Check if CORS headers allow unauthorized origins."""
        async with httpx.AsyncClient() as client:
            response = await client.options(
                url,
                headers={"Origin": "https://attacker.com"},
            )

            allow_origin = response.headers.get("Access-Control-Allow-Origin")
            allow_creds = response.headers.get("Access-Control-Allow-Credentials")

            findings = {}

            if allow_origin == "*" and allow_creds == "true":
                # Dangerous: wildcard + credentials
                findings["vulnerability"] = "CORS Wildcard + Credentials"
                findings["severity"] = "Critical"

            elif allow_origin == "*":
                findings["vulnerability"] = "CORS Wildcard (Moderate Risk)"
                findings["severity"] = "Medium"

            elif "attacker.com" in allow_origin:
                findings["vulnerability"] = "CORS Allows Attacker Domain"
                findings["severity"] = "High"

            return findings
```

---

## Pattern 5: Rate Limit Testing

```python
import time

class RateLimitTester:
    """Test if APIs enforce rate limits."""

    async def test_burst_requests(
        self,
        url: str,
        burst_size: int = 100,
        window_seconds: int = 1,
    ) -> dict:
        """Send burst of requests to detect missing rate limiting."""
        async with httpx.AsyncClient() as client:
            start = time.time()
            success_count = 0

            for _ in range(burst_size):
                try:
                    response = await client.get(url, timeout=5)
                    if response.status_code == 200:
                        success_count += 1
                except httpx.TimeoutException:
                    pass

            elapsed = time.time() - start

            if elapsed < window_seconds and success_count == burst_size:
                return {
                    "vulnerability": "Missing Rate Limiting",
                    "requests_per_second": success_count / elapsed,
                    "severity": "Medium",
                }

            return {"status": "rate_limited"}
```

---

## Pattern 6: Logic Flaw Detection

### Business Logic Bypasses

```python
class LogicFlawDetector:
    """Detect logic flaws in API behavior."""

    async def test_negative_balance(self, base_url: str) -> dict:
        """Test if system allows negative balance (logic flaw)."""
        async with httpx.AsyncClient() as client:
            # Create account with $100
            await client.post(f"{base_url}/account", json={"balance": 100})

            # Attempt to withdraw $200
            response = await client.post(
                f"{base_url}/withdraw",
                json={"amount": 200}
            )

            if response.status_code == 200:
                return {
                    "vulnerability": "Business Logic Flaw (Negative Balance)",
                    "severity": "High",
                }

            return {"status": "secure"}

    async def test_price_manipulation(self, base_url: str) -> dict:
        """Test if client-provided prices are accepted (logic flaw)."""
        response = await httpx.post(
            f"{base_url}/checkout",
            json={"item_id": 123, "price": 0.01}  # Manipulated price
        )

        if response.status_code == 200:
            return {
                "vulnerability": "Price Manipulation",
                "severity": "Critical",
            }

        return {"status": "secure"}
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Test on non-prod first** | Avoid disrupting live systems | Always use staging/test environment |
| **Document findings with proof** | Establish baseline for fixes | Include request/response in reports |
| **Prioritize by severity** | Focus remediation effort | CVSS scoring: Critical → High → Medium |
| **Verify fixes** | Prevent regression | Re-run fuzzer after patch |
| **Automated scanning** | Continuous security | Integrate into CI/CD pipeline |
| **Input validation everywhere** | Defense in depth | Whitelist allowed characters |
| **Use parameterized queries** | Prevent SQLi | Never concatenate SQL with user input |
| **Escape output** | Prevent XSS | HTML/JS/URL encode based on context |
| **Implement rate limiting** | Prevent abuse | Use token bucket or sliding window |
| **Log security events** | Audit trail | Log auth failures, fuzzing attempts |

---

## Security Rules (CRÍTICO)

1. **Test Only Authorized Systems**: Never fuzz without explicit permission (written authorization)
2. **Controlled Environment**: Always use staging/test environments first
3. **Report Findings Responsibly**: Include:
   - CVSS score
   - Proof of concept (redacted)
   - Remediation code
   - Timeline for patching
4. **Responsible Disclosure**: Notify vendor before public disclosure
5. **Log All Attempts**: Keep audit trail of fuzzing activities

---

## Implementation Checklist

- [ ] Set up isolated test environment
- [ ] Configure authentication for test account
- [ ] Deploy SQLi, XSS, auth bypass detection patterns
- [ ] Implement data exposure scanning
- [ ] Add CORS and rate limit testing
- [ ] Create automated scanning pipeline
- [ ] Establish baseline (what's "normal")
- [ ] Generate security report with findings
- [ ] Verify fixes with re-scanning
- [ ] Document remediation steps per finding
