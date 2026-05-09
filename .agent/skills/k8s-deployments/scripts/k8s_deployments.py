#!/usr/bin/env python3
"""
Kubernetes Deployments Skill

Genera manifests de Kubernetes siguiendo mejores prácticas.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field


@dataclass
class DeploymentConfig:
    """Configuración para un deployment de Kubernetes."""

    app_name: str
    image: str
    port: int = 8080
    replicas: int = 2
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
    env_vars: dict = field(default_factory=dict)
    namespace: str = "default"
    labels: dict = field(default_factory=dict)


def generate_deployment(config: DeploymentConfig) -> dict:
    """Genera un Deployment manifest."""
    labels = {"app": config.app_name, **config.labels}

    env_list = [{"name": k, "value": str(v)} for k, v in config.env_vars.items()]

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": config.app_name, "namespace": config.namespace, "labels": labels},
        "spec": {
            "replicas": config.replicas,
            "selector": {"matchLabels": {"app": config.app_name}},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [
                        {
                            "name": config.app_name,
                            "image": config.image,
                            "ports": [{"containerPort": config.port, "protocol": "TCP"}],
                            "env": env_list if env_list else None,
                            "resources": {
                                "requests": {
                                    "cpu": config.cpu_request,
                                    "memory": config.memory_request,
                                },
                                "limits": {"cpu": config.cpu_limit, "memory": config.memory_limit},
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": config.port},
                                "initialDelaySeconds": 30,
                                "periodSeconds": 10,
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/ready", "port": config.port},
                                "initialDelaySeconds": 5,
                                "periodSeconds": 5,
                            },
                        }
                    ]
                },
            },
        },
    }

    # Remove None values
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    if not container["env"]:
        del container["env"]

    return deployment


def generate_service(config: DeploymentConfig, service_type: str = "ClusterIP") -> dict:
    """Genera un Service manifest."""
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": config.app_name, "namespace": config.namespace},
        "spec": {
            "type": service_type,
            "selector": {"app": config.app_name},
            "ports": [{"port": config.port, "targetPort": config.port, "protocol": "TCP"}],
        },
    }


def generate_hpa(config: DeploymentConfig, min_replicas: int = 2, max_replicas: int = 10) -> dict:
    """Genera un HorizontalPodAutoscaler manifest."""
    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": f"{config.app_name}-hpa", "namespace": config.namespace},
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": config.app_name,
            },
            "minReplicas": min_replicas,
            "maxReplicas": max_replicas,
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {"type": "Utilization", "averageUtilization": 70},
                    },
                }
            ],
        },
    }


def generate_configmap(config: DeploymentConfig, data: dict) -> dict:
    """Genera un ConfigMap manifest."""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": f"{config.app_name}-config", "namespace": config.namespace},
        "data": {k: str(v) for k, v in data.items()},
    }


def generate_secret(config: DeploymentConfig, data: dict) -> dict:
    """Genera un Secret manifest (valores en base64)."""
    import base64

    encoded_data = {k: base64.b64encode(str(v).encode()).decode() for k, v in data.items()}
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": f"{config.app_name}-secret", "namespace": config.namespace},
        "type": "Opaque",
        "data": encoded_data,
    }


def generate_ingress(config: DeploymentConfig, host: str, tls: bool = False) -> dict:
    """Genera un Ingress manifest."""
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": f"{config.app_name}-ingress",
            "namespace": config.namespace,
            "annotations": {"nginx.ingress.kubernetes.io/rewrite-target": "/"},
        },
        "spec": {
            "rules": [
                {
                    "host": host,
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": config.app_name,
                                        "port": {"number": config.port},
                                    }
                                },
                            }
                        ]
                    },
                }
            ]
        },
    }

    if tls:
        ingress["spec"]["tls"] = [{"hosts": [host], "secretName": f"{config.app_name}-tls"}]

    return ingress


def generate_full_stack(config: DeploymentConfig, host: str | None = None) -> list:
    """Genera todos los manifests necesarios para un deployment completo."""
    manifests = [
        generate_deployment(config),
        generate_service(config),
        generate_hpa(config),
    ]

    if host:
        manifests.append(generate_ingress(config, host, tls=True))

    return manifests


def to_yaml(obj: dict) -> str:
    """Convierte un dict a YAML."""
    try:
        import yaml

        return yaml.dump(obj, default_flow_style=False, sort_keys=False)
    except ImportError:
        # Fallback simple sin PyYAML
        return json.dumps(obj, indent=2)


def validate_manifest(manifest: dict) -> list:
    """Valida un manifest de Kubernetes."""
    errors = []

    # Verificar campos requeridos
    if "apiVersion" not in manifest:
        errors.append("Missing 'apiVersion'")
    if "kind" not in manifest:
        errors.append("Missing 'kind'")
    if "metadata" not in manifest:
        errors.append("Missing 'metadata'")
    elif "name" not in manifest.get("metadata", {}):
        errors.append("Missing 'metadata.name'")

    # Validaciones específicas por tipo
    kind = manifest.get("kind", "")

    if kind == "Deployment":
        spec = manifest.get("spec", {})
        if "replicas" not in spec:
            errors.append("Deployment: Missing 'spec.replicas'")
        if "selector" not in spec:
            errors.append("Deployment: Missing 'spec.selector'")
        if "template" not in spec:
            errors.append("Deployment: Missing 'spec.template'")

        # Verificar recursos
        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        for i, container in enumerate(containers):
            if "resources" not in container:
                errors.append(f"Deployment: Container {i} missing resource limits")

    elif kind == "Service":
        spec = manifest.get("spec", {})
        if "selector" not in spec:
            errors.append("Service: Missing 'spec.selector'")
        if "ports" not in spec:
            errors.append("Service: Missing 'spec.ports'")

    return errors


def print_yaml_manifests(manifests: list):
    """Imprime manifests en formato YAML."""
    for i, manifest in enumerate(manifests):
        if i > 0:
            print("---")
        print(to_yaml(manifest))


def main():
    parser = argparse.ArgumentParser(
        description="Kubernetes Deployments Skill - Genera manifests de K8s"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Comando: generate
    gen_parser = subparsers.add_parser("generate", help="Genera manifests")
    gen_parser.add_argument("--app", "-a", required=True, help="Nombre de la aplicación")
    gen_parser.add_argument("--image", "-i", required=True, help="Imagen Docker")
    gen_parser.add_argument("--port", "-p", type=int, default=8080, help="Puerto")
    gen_parser.add_argument("--replicas", "-r", type=int, default=2, help="Réplicas")
    gen_parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    gen_parser.add_argument("--host", help="Host para Ingress")
    gen_parser.add_argument(
        "--type",
        "-t",
        choices=["deployment", "service", "hpa", "ingress", "full"],
        default="full",
        help="Tipo de manifest",
    )
    gen_parser.add_argument("--cpu-request", default="100m", help="CPU request")
    gen_parser.add_argument("--cpu-limit", default="500m", help="CPU limit")
    gen_parser.add_argument("--memory-request", default="128Mi", help="Memory request")
    gen_parser.add_argument("--memory-limit", default="512Mi", help="Memory limit")

    # Comando: validate
    val_parser = subparsers.add_parser("validate", help="Valida un manifest")
    val_parser.add_argument("file", help="Archivo YAML a validar")

    # Comando: template
    tmpl_parser = subparsers.add_parser("template", help="Muestra templates")
    tmpl_parser.add_argument(
        "--type",
        "-t",
        choices=["web-app", "api", "worker", "cronjob"],
        default="web-app",
        help="Tipo de template",
    )

    # Común
    parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "generate":
        config = DeploymentConfig(
            app_name=args.app,
            image=args.image,
            port=args.port,
            replicas=args.replicas,
            namespace=args.namespace,
            cpu_request=args.cpu_request,
            cpu_limit=args.cpu_limit,
            memory_request=args.memory_request,
            memory_limit=args.memory_limit,
        )

        if args.type == "deployment":
            manifests = [generate_deployment(config)]
        elif args.type == "service":
            manifests = [generate_service(config)]
        elif args.type == "hpa":
            manifests = [generate_hpa(config)]
        elif args.type == "ingress":
            if not args.host:
                print("Error: --host requerido para Ingress")
                return 1
            manifests = [generate_ingress(config, args.host)]
        else:  # full
            manifests = generate_full_stack(config, args.host)

        if args.json:
            print(json.dumps(manifests, indent=2))
        else:
            print_yaml_manifests(manifests)

    elif args.command == "validate":
        try:
            import yaml

            with open(args.file) as f:
                docs = list(yaml.safe_load_all(f))
        except ImportError:
            print("Error: PyYAML no instalado. Instalar con: pip install pyyaml")
            return 1
        except Exception as e:
            print(f"Error leyendo archivo: {e}")
            return 1

        all_errors = []
        for i, doc in enumerate(docs):
            if doc:
                errors = validate_manifest(doc)
                for error in errors:
                    all_errors.append(f"Document {i}: {error}")

        if all_errors:
            print("Errores de validación:")
            for error in all_errors:
                print(f"  - {error}")
            return 1
        else:
            print("✓ Manifest válido")
            return 0

    elif args.command == "template":
        templates = {
            "web-app": {
                "description": "Aplicación web con Ingress y HPA",
                "components": ["Deployment", "Service", "Ingress", "HPA"],
                "example": "k8s_deployments.py generate --app webapp --image nginx:latest --port 80 --host example.com",
            },
            "api": {
                "description": "API backend con ClusterIP",
                "components": ["Deployment", "Service", "HPA", "ConfigMap"],
                "example": "k8s_deployments.py generate --app api --image myapi:latest --port 8080",
            },
            "worker": {
                "description": "Worker sin Service expuesto",
                "components": ["Deployment", "ConfigMap", "Secret"],
                "example": "k8s_deployments.py generate --app worker --image worker:latest --type deployment",
            },
            "cronjob": {
                "description": "Job programado",
                "components": ["CronJob"],
                "note": "Usar kubectl create cronjob para este tipo",
            },
        }

        if args.json:
            print(json.dumps(templates, indent=2))
        else:
            tmpl = templates.get(args.type, {})
            print(f"\n{'=' * 60}")
            print(f" Template: {args.type.upper()}")
            print(f"{'=' * 60}\n")
            print(f"Descripción: {tmpl.get('description', 'N/A')}")
            print(f"Componentes: {', '.join(tmpl.get('components', []))}")
            if "example" in tmpl:
                print("\nEjemplo:")
                print(f"  {tmpl['example']}")
            if "note" in tmpl:
                print(f"\nNota: {tmpl['note']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
