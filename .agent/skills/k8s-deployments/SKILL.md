---
type: feature
name: k8s-deployments
description: Expert in generating and managing production-grade Kubernetes deployments. YAML manifests, resource optimization, auto-scaling, health checks, and GitOps workflows.
category: devops
version: 2.1.0
tags:
---
  - kubernetes
  - k8s
  - deployment
  - yaml
  - devops
  - orchestration
  - infrastructure
requires:
  tools:
    - kubectl
    - kustomize
    - helm
  optional:
    - flux
    - argocd
    - kubectx
triggers:
  - "kubernetes|k8s deployment|manifest"
  - "helm chart|kustomize|kubernetes config"
  - "rolling update|pod scaling|container orchestration"
---

# Kubernetes Deployments

Master production-grade Kubernetes deployments with proper resource management, auto-scaling, and reliability patterns. Deploy applications safely with health checks, rolling updates, and monitoring.

## Use this skill when

- Generating Deployment manifests for containerized apps
- Configuring resource requests/limits for efficient scheduling
- Setting up Horizontal Pod Autoscaler (HPA) for load-based scaling
- Implementing health checks (liveness/readiness probes)
- Configuring Ingress for external traffic routing
- Managing ConfigMaps and Secrets for configuration
- Enabling rolling updates and rollback strategies
- Multi-environment deployments (dev/staging/production)
- GitOps-based deployment workflows (Flux, ArgoCD)

## Do not use this skill when

- Task is unrelated to Kubernetes deployment
- Managing lower-level infrastructure (node/network configuration)
- Deploying non-containerized applications

## Core Manifest Patterns

### 1. Basic Deployment (Web Application)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: production
  labels:
    app: myapp
    version: v1
spec:
  replicas: 3  # Number of pod copies
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1      # Keep 1 pod available during update
      maxSurge: 1            # Max 1 extra pod during update
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
        version: v1
    spec:
      containers:
      - name: myapp
        image: myapp:v1.2.3  # Use specific version, not :latest
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP

        # Resource requests & limits
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"         # 0.25 CPU cores
          limits:
            memory: "512Mi"
            cpu: "500m"

        # Health checks
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5

        # Environment variables
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url

        # Volume mounts
        volumeMounts:
        - name: config
          mountPath: /etc/config
          readOnly: true

      # Security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsReadOnlyRootFilesystem: true

      # Volumes
      volumes:
      - name: config
        configMap:
          name: myapp-config
```

### 2. Service (Load Balancing)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp-service
  namespace: production
spec:
  type: ClusterIP          # Internal only
  # type: LoadBalancer    # External (cloud provider LB)
  # type: NodePort        # External via node port
  selector:
    app: myapp
  ports:
  - name: http
    port: 80              # External port
    targetPort: 8080      # Container port
    protocol: TCP
  sessionAffinity: None   # Or "ClientIP" for sticky sessions
```

### 3. Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70      # Scale when CPU > 70%
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80      # Scale when memory > 80%
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
      policies:
      - type: Percent
        value: 50                    # Scale down by 50% max
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0     # Scale up immediately
      policies:
      - type: Percent
        value: 100                   # Double pods if needed
        periodSeconds: 30
```

### 4. ConfigMap & Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
  namespace: production
data:
  app.properties: |
    server.port=8080
    logging.level=INFO
  database.json: |
    {
      "pool_size": 20,
      "max_connections": 100
    }
---
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: production
type: Opaque
stringData:  # Use for development (readable)
  url: "postgresql://user:pass@db:5432/mydb"
  # In production: use base64-encoded 'data' instead
```

### 5. Ingress (HTTP Routing)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: production
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - myapp.example.com
    secretName: myapp-tls
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: myapp-service
            port:
              number: 80
      - path: /admin
        pathType: Prefix
        backend:
          service:
            name: myapp-admin
            port:
              number: 8081
```

## Resource Management Best Practices

### CPU & Memory Requests/Limits

| Tier | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|------------|-----------|----------------|--------------|
| **Small** | 100m | 500m | 128Mi | 256Mi |
| **Medium** | 250m | 1000m | 256Mi | 512Mi |
| **Large** | 500m | 2000m | 512Mi | 2Gi |
| **XL** | 1000m | 4000m | 1Gi | 4Gi |

**Rules:**
- Always set `requests` (scheduler needs this to place pod)
- Set `limits` to prevent pod eviction
- `limit ≥ request` always
- Real-world: `limit = 2-3x request`

### Namespace Isolation

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    requests.cpu: "10"
    requests.memory: "20Gi"
    limits.cpu: "20"
    limits.memory: "40Gi"
    pods: "100"
```

## Deployment Strategies

### Rolling Update (Default - Zero Downtime)

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1    # Min 1 pod always running
    maxSurge: 1          # Max 1 pod extra during update
# Timeline: 0% → 33% → 67% → 100% uptime
```

### Blue-Green Deployment (Instant Rollback)

```yaml
# Deploy new version (green) alongside old (blue)
# Once green is healthy, switch traffic instantly
# Rollback: switch back to blue immediately
```

### Canary Deployment (Progressive Traffic)

```yaml
# Deploy new version to small % of traffic
# Monitor metrics, gradually increase if healthy
# Rollback instantly if issues detected
```

## Health Check Patterns

### Liveness Probe (Restart Dead Pod)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30  # Wait 30s before first check
  periodSeconds: 10        # Check every 10s
  timeoutSeconds: 5        # Fail if no response in 5s
  failureThreshold: 3      # Restart after 3 failures
```

### Readiness Probe (Traffic Routing)

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 1      # Remove from service immediately
```

### Startup Probe (Slow-starting Apps)

```yaml
startupProbe:
  httpGet:
    path: /health
    port: 8080
  failureThreshold: 30     # 30 checks × 10s = 5 min startup window
  periodSeconds: 10
```

## Kubectl Commands

```bash
# Deployment operations
kubectl apply -f deployment.yaml         # Deploy/update
kubectl rollout status deployment/myapp  # Watch rollout
kubectl rollout undo deployment/myapp    # Rollback
kubectl scale deployment/myapp --replicas=5

# Debugging
kubectl logs pod/myapp-xyz               # Pod logs
kubectl describe pod/myapp-xyz           # Pod details
kubectl exec -it pod/myapp-xyz -- /bin/sh  # Shell access
kubectl port-forward pod/myapp-xyz 8080:8080  # Local access

# Resource management
kubectl top pod                          # CPU/memory usage
kubectl get events -n production         # System events
kubectl apply -f - < <(cat deployment.yaml | envsubst)  # Env vars
```

## Performance Checklist

- [ ] **REQUESTS/LIMITS**: Set for all containers
- [ ] **HEALTH CHECKS**: Liveness + readiness configured
- [ ] **HPA**: Auto-scaling configured for load
- [ ] **NAMESPACE**: Isolated environments with resource quotas
- [ ] **SECURITY**: Non-root user, read-only filesystem
- [ ] **LABELS**: Proper labels for selectors and monitoring
- [ ] **STRATEGY**: Rolling updates configured
- [ ] **MONITORING**: Prometheus metrics exposed
- [ ] **LOGGING**: Structured logs to stdout/stderr

## Anti-Patterns

❌ Using `:latest` tag (unpredictable versions)
❌ No resource requests/limits (scheduling fails)
❌ No health checks (zombie pods running)
❌ Running as root (security risk)
❌ Large images (slow deployments, wasted storage)
❌ Storing secrets in manifests (credentials exposed)

## Best Practices

✅ **Use specific image tags** — Never `:latest`
✅ **Set requests correctly** — Scheduler depends on this
✅ **Health checks always** — Liveness + readiness
✅ **Resource limits** — Prevent runaway containers
✅ **Gradual rollouts** — maxUnavailable/maxSurge
✅ **Secrets management** — Use Secret objects, not ConfigMaps
✅ **Namespace isolation** — Separate concerns
✅ **Monitor everything** — Prometheus + dashboards

## Resources

- **Kubernetes docs**: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- **Best practices**: https://kubernetes.io/docs/concepts/configuration/overview/
- **Security**: https://kubernetes.io/docs/concepts/security/
- **Kustomize**: https://kustomize.io/
- **Helm**: https://helm.sh/
