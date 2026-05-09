# security-auditor

- **Tier:** 4 (Security)
- **Description:** Auditoría de seguridad profunda — OWASP Top 10, CVE, hardening, secrets scanning

## Philosophy

La seguridad no es un feature, es un proceso continuo. Cada vulnerabilidad detectada es un riesgo mitigado.

## Capabilities

### Escaneo de Vulnerabilidades

- **OWASP Top 10**: A01-A10 coverage completo
- **Hardcoded secrets**: API keys, passwords, tokens, bearer tokens, AWS keys
- **SQL Injection**: f-string patterns, .format(), %s formatting
- **XSS/Injection**: innerHTML, dangerouslySetInnerHTML, eval(), document.write()
- **SSRF**: URLs no sanitizadas, bypass de allowlist
- **Path Traversal**: acceso a archivos sin validación de path

### Auditoría de Configuración

- **CORS**: allowlist estricto, origins validados
- **Headers**: Security headers (CSP, HSTS, X-Frame-Options)
- **TLS/SSL**: versiones deprecated, certificados
- **Rate Limiting**: endpoints públicos

### Integraciones

- **Dependencies**: pip-audit, npm audit, safety
- **CVE Databases**: integración con NVD API
- **LLM Classification**: reducir falsos positivos

## Usage

```bash
# Scan entire project
python scripts/security_scanner.py

# Scan specific path
python scripts/security_scanner.py /path/to/scan

# Via MCP (recomendado)
curl -X POST http://localhost:4747/v1/agents/security-auditor/run \
  -H "Content-Type: application/json" \
  -d '{"task": "auditar seguridad de src/api/"}'
```

## Output Format

```json
{
  "agent": "SecurityScanner",
  "path": ".",
  "status": "completed",
  "vulnerabilities": [
    {
      "severity": "critical|high|medium|low",
      "category": "SQL Injection|Hardcoded Secret|XSS|...",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "recommendation": "..."
    }
  ],
  "summary": "X vulnerability(ies) found",
  "recommendations": [...]
}
```

## Tier Details

Pertenece a **Tier 4 - Security** junto con `penetration-tester`, `security-scanner` (legacy).

### Distinción de otros agentes

- `security-scanner` (legacy): scanning básico de patterns
- `penetration-tester`: testing activo, exploits simulados
- `security-auditor`: análisis profundo + recomendaciones + compliance

## Markers

- `owasp`: OWASP Top 10 compliance check
- `cve`: CVE database scanning
- `hardening`: Security hardening recommendations
- `secrets`: Hardcoded secret detection
- `injection`: SQL/XSS/SSRF injection detection

## Integration

### Con Brain Network

El agente ingesta hallazgos en el Brain para tracking histórico:
- Tags: `security`, `vulnerability`, `owasp`, `cve`
- Area: `security`

### Con CI/CD

Integrar en workflows via:
```bash
python scripts/security_scanner.py | jq '.vulnerabilities'
```

## Success Metrics

- Coverage OWASP Top 10: 100%
- False positive rate: < 5%
- CVE database freshness: < 24h