---
name: devops-advanced
description: Advanced DevOps practices. Infrastructure as Code, Terraform, Ansible, Kubernetes, CI/CD, GitOps, observability, incident response.
type: feature
category: devops
tags: [devops, infrastructure, terraform, kubernetes, ansible, cicd, gitops, observability]
version: 1.0.0
---

# DevOps Advanced

> Automate everything, monitor everything, respond fast.
> **Infrastructure as Code is non-negotiable.**

---

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `terraform-patterns.md` | HCL patterns, modules, state management | Infrastructure provisioning |
| `ansible-playbooks.md` | Playbook structure, handlers, roles | Configuration management |
| `kubernetes-advanced.md` | Operators, CRDs, networking, storage | K8s production deployments |
| `cicd-pipelines.md` | GitHub Actions, GitLab CI/CD, testing gates | Automation workflows |
| `gitops.md` | ArgoCD, flux, environment parity | Declarative deployments |
| `observability.md` | Prometheus, Loki, Grafana, SLOs | Monitoring and alerting |
| `incident-response.md` | Runbooks, incident severity, postmortems | On-call excellence |
| `cost-optimization.md` | Resource requests, autoscaling, reserved capacity | Reducing cloud spend |

---

## 🔗 Related Skills

| Need | Skill |
|------|-------|
| Compliance | `@[skills/compliance-governance]` |
| Security | `@[skills/security-testing]` |
| Data pipelines | `@[skills/data-engineering]` |
| Architecture | `@[skills/architecture-patterns]` |

---

## ✅ Infrastructure Readiness Checklist

Before production deployment:

- [ ] **Infrastructure as Code version controlled?**
- [ ] **State management secured?** (backend encryption, locking)
- [ ] **Secrets management configured?** (Vault, AWS Secrets)
- [ ] **Networking isolated?** (security groups, NACLs)
- [ ] **Autoscaling configured?** (min/max replicas)
- [ ] **Monitoring/alerting setup?**
- [ ] **Backup/restore tested?**
- [ ] **Disaster recovery plan documented?**
- [ ] **Cost projections reviewed?**
- [ ] **Access controls enforced?** (RBAC)
- [ ] **Network policies defined?** (K8s)

---

## Terraform Project Structure

```
infrastructure/
├── terraform.tfvars          # Environment variables
├── variables.tf              # Input variable definitions
├── outputs.tf                # Output definitions
├── locals.tf                 # Local values
├── main.tf                   # Main configuration
├── modules/
│   ├── vpc/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── ecs/
│   │   └── ...
│   └── rds/
│       └── ...
├── environments/
│   ├── dev/
│   │   └── terraform.tfvars
│   ├── staging/
│   │   └── terraform.tfvars
│   └── prod/
│       └── terraform.tfvars
└── .terraform.lock.hcl       # Dependency lock file
```

---

## Terraform Best Practices

### State Management
```hcl
# Use remote backend (never local in prod)
terraform {
  backend "s3" {
    bucket         = "my-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "tf-locks"
  }
}
```

### Module Pattern
```hcl
# Reusable module
module "vpc" {
  source = "./modules/vpc"

  name             = "prod"
  cidr_block       = var.vpc_cidr
  availability_zones = data.aws_availability_zones.available.names

  tags = var.common_tags
}
```

---

## Kubernetes Architecture

### Namespace Isolation
```yaml
# Separate environments
namespaces:
  - production    # Business logic
  - staging       # Pre-prod testing
  - monitoring    # Prometheus, Loki
  - ingress       # Nginx controller
  - system        # Kubernetes core
```

### GitOps Flow
```
Git (Source of Truth)
  ↓
  CI Pipeline (test, build image)
  ↓
  Push to Registry
  ↓
  GitOps Controller (ArgoCD)
  ↓
  Sync Kubernetes State
```

---

## CI/CD Pipeline Template

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Testing gates
      - run: npm ci && npm run test
      - run: npm run lint
      - run: npm run security-audit

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Build and push image
      - run: docker build -t app:${{ github.sha }} .
      - run: docker push app:${{ github.sha }}

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Deploy via GitOps
      - run: |
          kustomize edit set image app=app:${{ github.sha }}
          git commit -am "Deploy ${{ github.sha }}"
          git push
```

---

## Observability Stack

### Metrics (Prometheus)
```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### Logs (Loki)
```yaml
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    pipeline_stages:
      - json:
          expressions:
            level: level
            message: message
      - labels:
          level:
```

### Traces (Jaeger/Tempo)
```yaml
exporters:
  jaeger:
    endpoint: http://jaeger:14250
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
```

---

## SLO/SLI Framework

| Component | SLI (Indicator) | SLO (Objective) |
|-----------|-----------------|-----------------|
| API Availability | Successful responses / Total | 99.9% uptime |
| API Performance | P99 latency | < 500ms |
| Data Pipeline | On-time completion | 99% within SLA |
| Database | Write latency | < 100ms p95 |
| Cost | Spend variance | ±10% of budget |

---

## Incident Response Runbook

```
Incident Detected
  ↓
Severity Assessment (P1/P2/P3)
  ↓
P1? → Declare SEV-1, page on-call
P2? → Create incident thread
P3? → Log for later review
  ↓
Mitigation (stop the bleeding)
  ↓
Root Cause Analysis (why did it happen?)
  ↓
Prevention (how do we stop it?)
  ↓
Postmortem (document lessons learned)
  ↓
Action Items (tracked for closure)
```

---

## ❌ Anti-Patterns

**DON'T:**
- Hardcode configuration in code
- Manual infrastructure changes
- Skip testing in CI/CD
- Use same credentials for all environments
- Ignore resource quotas
- Deploy without automated rollback
- Keep unnecessary services running (costs!)
- Skip postmortems
- Make on-call unsustainable

**DO:**
- Everything as code
- Automate everything
- Gate deployments with tests
- Use secrets management
- Set resource requests/limits
- Implement graceful shutdown
- Monitor costs religiously
- Blameless postmortems
- Rotate on-call fairly

---

## Tools & Commands

### Terraform
```bash
terraform init              # Initialize backend
terraform plan              # Preview changes
terraform apply             # Apply changes
terraform destroy           # Destroy resources
terraform import <res> <id> # Import existing resource
```

### Ansible
```bash
ansible-playbook site.yml                    # Run playbook
ansible <group> -m ping                      # Test connectivity
ansible-vault encrypt secrets.yml            # Encrypt secrets
ansible-inventory --list -y                  # List inventory
```

### Kubernetes
```bash
kubectl apply -f manifest.yaml               # Deploy resource
kubectl port-forward svc/api 8080:80        # Port forwarding
kubectl logs -f deployment/api               # Stream logs
kubectl describe node <name>                 # Debug node
```

---

## Script

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/tf_cost_analyzer.py` | Estimate Terraform costs | `python scripts/tf_cost_analyzer.py --plan plan.json` |
| `scripts/k8s_security_audit.py` | Audit K8s security | `python scripts/k8s_security_audit.py --cluster prod` |
| `scripts/incident_postmortem_generator.py` | Generate postmortem template | `python scripts/incident_postmortem_generator.py --incident-id SEV-1-123` |
