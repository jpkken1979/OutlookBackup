#!/usr/bin/env python3
"""
Serverless Architect Agent

Diseña y genera arquitecturas serverless para AWS Lambda, Azure Functions, etc.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FunctionConfig:
    """Configuración de una función serverless."""

    name: str
    runtime: str
    handler: str
    memory_mb: int = 256
    timeout_sec: int = 30
    trigger: str = "http"
    environment: dict = field(default_factory=dict)


@dataclass
class CostEstimate:
    """Estimación de costos serverless."""

    invocations_per_month: int
    avg_duration_ms: int
    memory_mb: int
    requests_cost: float
    compute_cost: float
    total_monthly: float


# Pricing AWS Lambda (us-east-1)
AWS_LAMBDA_PRICING = {
    "request_per_million": 0.20,
    "gb_second": 0.0000166667,
    "free_tier_requests": 1_000_000,
    "free_tier_gb_seconds": 400_000,
}


# Templates de funciones
FUNCTION_TEMPLATES = {
    "aws_python": '''import json
import logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    {description}

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        API Gateway response object
    """
    logger.info(f"Received event: {{json.dumps(event)}}")

    try:
        # Parse request
        body = json.loads(event.get('body', '{{}}')) if event.get('body') else {{}}

        # Implementar: lógica de negocio
        result = {{"message": "Success"}}

        return {{
            'statusCode': 200,
            'headers': {{
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            }},
            'body': json.dumps(result)
        }}

    except Exception as e:
        logger.error(f"Error: {{str(e)}}")
        return {{
            'statusCode': 500,
            'headers': {{'Content-Type': 'application/json'}},
            'body': json.dumps({{'error': str(e)}})
        }}
''',
    "aws_typescript": """import {{ APIGatewayProxyEvent, APIGatewayProxyResult, Context }} from 'aws-lambda';

/**
 * {description}
 */
export const handler = async (
  event: APIGatewayProxyEvent,
  context: Context
): Promise<APIGatewayProxyResult> => {{
  console.log('Received event:', JSON.stringify(event, null, 2));

  try {{
    // Parse request body
    const body = event.body ? JSON.parse(event.body) : {{}};

    // Implementar: lógica de negocio
    const result = {{ message: 'Success' }};

    return {{
      statusCode: 200,
      headers: {{
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      }},
      body: JSON.stringify(result),
    }};
  }} catch (error) {{
    console.error('Error:', error);
    return {{
      statusCode: 500,
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ error: (error as Error).message }}),
    }};
  }}
}};
""",
    "sqs_handler": '''import json
import logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    SQS Queue Handler - {name}
    Processes messages from SQS queue.
    """
    logger.info(f"Processing {{len(event['Records'])}} messages")

    failed_messages = []

    for record in event['Records']:
        try:
            message_id = record['messageId']
            body = json.loads(record['body'])

            logger.info(f"Processing message {{message_id}}")

            # Implementar: procesar mensaje
            process_message(body)

        except Exception as e:
            logger.error(f"Failed to process {{record['messageId']}}: {{e}}")
            failed_messages.append({{
                'itemIdentifier': record['messageId']
            }})

    # Return failed messages for retry
    return {{'batchItemFailures': failed_messages}}


def process_message(body: dict):
    """Process a single message."""
    # Implementar: lógica de negocio
    pass
''',
    "dynamodb_stream": '''import json
import logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> None:
    """
    DynamoDB Streams Handler - {name}
    Processes DynamoDB stream events.
    """
    for record in event['Records']:
        event_name = record['eventName']  # INSERT, MODIFY, REMOVE
        table_name = record['eventSourceARN'].split('/')[1]

        logger.info(f"{{event_name}} on {{table_name}}")

        if event_name == 'INSERT':
            new_item = deserialize(record['dynamodb']['NewImage'])
            handle_insert(new_item)

        elif event_name == 'MODIFY':
            old_item = deserialize(record['dynamodb']['OldImage'])
            new_item = deserialize(record['dynamodb']['NewImage'])
            handle_modify(old_item, new_item)

        elif event_name == 'REMOVE':
            old_item = deserialize(record['dynamodb']['OldImage'])
            handle_delete(old_item)


def deserialize(item: dict) -> dict:
    """Convert DynamoDB item to Python dict."""
    # Simplified - use boto3.dynamodb.types.TypeDeserializer in production
    result = {{}}
    for key, value in item.items():
        if 'S' in value:
            result[key] = value['S']
        elif 'N' in value:
            result[key] = float(value['N'])
        elif 'BOOL' in value:
            result[key] = value['BOOL']
    return result


def handle_insert(item: dict):
    logger.info(f"New item: {{item}}")
    # Implementar: manejar inserción


def handle_modify(old_item: dict, new_item: dict):
    logger.info(f"Modified: {{old_item}} -> {{new_item}}")
    # Implementar: manejar modificación


def handle_delete(item: dict):
    logger.info(f"Deleted: {{item}}")
    # Implementar: manejar eliminación
''',
}

# Templates de IaC
IAC_TEMPLATES = {
    "serverless_yml": """service: {service_name}

frameworkVersion: '3'

provider:
  name: aws
  runtime: {runtime}
  stage: ${{opt:stage, 'dev'}}
  region: ${{opt:region, 'us-east-1'}}

  environment:
    STAGE: ${{self:provider.stage}}

  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - dynamodb:GetItem
            - dynamodb:PutItem
            - dynamodb:UpdateItem
            - dynamodb:DeleteItem
            - dynamodb:Query
            - dynamodb:Scan
          Resource:
            - !GetAtt Table.Arn

functions:
{functions}

resources:
  Resources:
    Table:
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${{self:service}}-${{self:provider.stage}}
        BillingMode: PAY_PER_REQUEST
        AttributeDefinitions:
          - AttributeName: id
            AttributeType: S
        KeySchema:
          - AttributeName: id
            KeyType: HASH

plugins:
  - serverless-offline
  - serverless-prune-plugin

custom:
  prune:
    automatic: true
    number: 3
""",
    "sam_template": """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: {service_name}

Globals:
  Function:
    Timeout: 30
    Runtime: {runtime}
    MemorySize: 256
    Tracing: Active
    Environment:
      Variables:
        STAGE: !Ref Stage

Parameters:
  Stage:
    Type: String
    Default: dev
    AllowedValues:
      - dev
      - staging
      - prod

Resources:
{resources}

  Table:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "${{AWS::StackName}}-table"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH

Outputs:
  ApiUrl:
    Description: API Gateway URL
    Value: !Sub "https://${{ServerlessRestApi}}.execute-api.${{AWS::Region}}.amazonaws.com/${{Stage}}/"
""",
    "terraform": """# {service_name} - Terraform

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

variable "stage" {{
  default = "dev"
}}

variable "region" {{
  default = "us-east-1"
}}

provider "aws" {{
  region = var.region
}}

# Lambda Function
resource "aws_lambda_function" "{function_name}" {{
  function_name = "{service_name}-${{var.stage}}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "{handler}"
  runtime       = "{runtime}"
  timeout       = 30
  memory_size   = 256

  filename         = "lambda.zip"
  source_code_hash = filebase64sha256("lambda.zip")

  environment {{
    variables = {{
      STAGE = var.stage
    }}
  }}

  tracing_config {{
    mode = "Active"
  }}
}}

# IAM Role
resource "aws_iam_role" "lambda_role" {{
  name = "{service_name}-${{var.stage}}-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {{
        Service = "lambda.amazonaws.com"
      }}
    }}]
  }})
}}

# CloudWatch Logs
resource "aws_iam_role_policy_attachment" "lambda_logs" {{
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}}

# API Gateway
resource "aws_apigatewayv2_api" "api" {{
  name          = "{service_name}-${{var.stage}}"
  protocol_type = "HTTP"
}}

resource "aws_apigatewayv2_stage" "stage" {{
  api_id      = aws_apigatewayv2_api.api.id
  name        = var.stage
  auto_deploy = true
}}

resource "aws_apigatewayv2_integration" "lambda" {{
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.{function_name}.invoke_arn
  integration_method = "POST"
}}

resource "aws_apigatewayv2_route" "route" {{
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "ANY /{{proxy+}}"
  target    = "integrations/${{aws_apigatewayv2_integration.lambda.id}}"
}}

resource "aws_lambda_permission" "api_gw" {{
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.{function_name}.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${{aws_apigatewayv2_api.api.execution_arn}}/*/*"
}}

output "api_url" {{
  value = aws_apigatewayv2_stage.stage.invoke_url
}}
""",
}

# Triggers disponibles
TRIGGERS = {
    "http": "API Gateway HTTP endpoint",
    "sqs": "SQS Queue messages",
    "sns": "SNS Topic notifications",
    "s3": "S3 Bucket events",
    "dynamodb": "DynamoDB Streams",
    "schedule": "CloudWatch Events schedule",
    "kinesis": "Kinesis Data Streams",
    "eventbridge": "EventBridge events",
}


def estimate_cost(invocations: int, avg_duration_ms: int, memory_mb: int) -> CostEstimate:
    """Estima el costo mensual de una función Lambda."""

    # Convertir a GB-segundos
    duration_sec = avg_duration_ms / 1000
    memory_gb = memory_mb / 1024
    gb_seconds = invocations * duration_sec * memory_gb

    # Aplicar free tier
    billable_requests = max(0, invocations - AWS_LAMBDA_PRICING["free_tier_requests"])
    billable_gb_seconds = max(0, gb_seconds - AWS_LAMBDA_PRICING["free_tier_gb_seconds"])

    # Calcular costos
    requests_cost = (billable_requests / 1_000_000) * AWS_LAMBDA_PRICING["request_per_million"]
    compute_cost = billable_gb_seconds * AWS_LAMBDA_PRICING["gb_second"]
    total = requests_cost + compute_cost

    return CostEstimate(
        invocations_per_month=invocations,
        avg_duration_ms=avg_duration_ms,
        memory_mb=memory_mb,
        requests_cost=round(requests_cost, 2),
        compute_cost=round(compute_cost, 2),
        total_monthly=round(total, 2),
    )


def generate_function(
    name: str, trigger: str, language: str = "python", description: str = ""
) -> str:
    """Genera código de función Lambda."""

    if trigger == "sqs":
        template = FUNCTION_TEMPLATES["sqs_handler"]
    elif trigger == "dynamodb":
        template = FUNCTION_TEMPLATES["dynamodb_stream"]
    elif language == "typescript":
        template = FUNCTION_TEMPLATES["aws_typescript"]
    else:
        template = FUNCTION_TEMPLATES["aws_python"]

    return template.format(name=name, description=description or f"Lambda function: {name}")


def generate_serverless_yml(service_name: str, functions: list, runtime: str = "python3.11") -> str:
    """Genera serverless.yml."""

    functions_yaml = ""
    for func in functions:
        func_config = f"""  {func["name"]}:
    handler: src/{func["name"]}.handler
    events:
"""
        if func.get("trigger") == "http":
            func_config += f"""      - http:
          path: /{func["name"]}
          method: any
          cors: true
"""
        elif func.get("trigger") == "sqs":
            func_config += f"""      - sqs:
          arn: !GetAtt {func["name"]}Queue.Arn
          batchSize: 10
"""
        elif func.get("trigger") == "schedule":
            func_config += """      - schedule:
          rate: rate(5 minutes)
          enabled: true
"""
        functions_yaml += func_config

    return IAC_TEMPLATES["serverless_yml"].format(
        service_name=service_name, runtime=runtime, functions=functions_yaml
    )


def generate_terraform(service_name: str, function_name: str, runtime: str = "python3.11") -> str:
    """Genera configuración Terraform."""

    handler = "main.handler" if "python" in runtime else "index.handler"

    return IAC_TEMPLATES["terraform"].format(
        service_name=service_name,
        function_name=function_name.replace("-", "_"),
        runtime=runtime,
        handler=handler,
    )


def analyze_for_serverless(project_path: Path) -> dict:
    """Analiza un proyecto para determinar si es apto para serverless."""

    analysis = {
        "serverless_ready": True,
        "score": 100,
        "recommendations": [],
        "concerns": [],
        "suggested_functions": [],
    }

    # Buscar indicadores
    has_db_connection = False
    has_long_running = False
    has_websocket = False
    has_file_storage = False

    # Revisar archivos
    for py_file in project_path.rglob("*.py"):
        try:
            content = py_file.read_text()

            if "psycopg" in content or "mysql" in content or "sqlalchemy" in content:
                has_db_connection = True

            if "websocket" in content.lower() or "socket.io" in content.lower():
                has_websocket = True

            if "time.sleep" in content and "60" in content:
                has_long_running = True

            if "open(" in content and ("'w'" in content or "'wb'" in content):
                has_file_storage = True

        except Exception:
            continue

    # Evaluar
    if has_db_connection:
        analysis["recommendations"].append("Considerar usar DynamoDB o Aurora Serverless")
        analysis["score"] -= 10

    if has_websocket:
        analysis["concerns"].append("WebSockets requieren API Gateway WebSocket API")
        analysis["recommendations"].append("Usar AWS API Gateway WebSocket o servicio dedicado")
        analysis["score"] -= 20

    if has_long_running:
        analysis["concerns"].append("Procesos largos pueden exceder timeout de Lambda (15 min)")
        analysis["recommendations"].append(
            "Dividir en funciones más pequeñas o usar Step Functions"
        )
        analysis["score"] -= 15

    if has_file_storage:
        analysis["recommendations"].append(
            "Usar S3 para almacenamiento de archivos (Lambda es efímero)"
        )
        analysis["score"] -= 5

    # Determinar si es apto
    analysis["serverless_ready"] = analysis["score"] >= 60

    # Sugerir funciones
    analysis["suggested_functions"] = [
        {"name": "api", "trigger": "http", "description": "API endpoints"},
        {"name": "worker", "trigger": "sqs", "description": "Background processing"},
    ]

    return analysis


def main():
    parser = argparse.ArgumentParser(
        description="Serverless Architect - Diseña arquitecturas serverless"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analiza proyecto para serverless")
    analyze_parser.add_argument("--project", "-p", default=".", help="Ruta al proyecto")

    # init
    init_parser = subparsers.add_parser("init", help="Inicializa proyecto serverless")
    init_parser.add_argument("--provider", choices=["aws", "azure", "gcp"], default="aws")
    init_parser.add_argument(
        "--framework", choices=["serverless", "sam", "sst"], default="serverless"
    )
    init_parser.add_argument("--name", "-n", required=True, help="Nombre del servicio")

    # function
    func_parser = subparsers.add_parser("function", help="Genera función Lambda")
    func_parser.add_argument("--name", "-n", required=True, help="Nombre de la función")
    func_parser.add_argument("--trigger", "-t", choices=list(TRIGGERS.keys()), default="http")
    func_parser.add_argument("--language", "-l", choices=["python", "typescript"], default="python")

    # cost
    cost_parser = subparsers.add_parser("cost", help="Estima costos")
    cost_parser.add_argument(
        "--invocations", "-i", type=int, required=True, help="Invocaciones/mes"
    )
    cost_parser.add_argument(
        "--duration", "-d", type=int, required=True, help="Duración promedio (ms)"
    )
    cost_parser.add_argument("--memory", "-m", type=int, default=256, help="Memoria (MB)")

    # iac
    iac_parser = subparsers.add_parser("iac", help="Genera IaC")
    iac_parser.add_argument("--provider", choices=["aws"], default="aws")
    iac_parser.add_argument(
        "--format", "-f", choices=["serverless", "terraform", "sam"], required=True
    )
    iac_parser.add_argument("--name", "-n", required=True, help="Nombre del servicio")

    # triggers
    subparsers.add_parser("triggers", help="Lista triggers disponibles")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "analyze":
        project_path = Path(args.project)
        analysis = analyze_for_serverless(project_path)

        if args.json:
            output = json.dumps(analysis, indent=2)
        else:
            status = "✅ APTO" if analysis["serverless_ready"] else "⚠️ REQUIERE CAMBIOS"
            print(f"\n{'=' * 60}")
            print(" ANÁLISIS SERVERLESS")
            print(f"{'=' * 60}")
            print(f"\nEstado: {status}")
            print(f"Score: {analysis['score']}/100")

            if analysis["concerns"]:
                print("\n🔴 Concerns:")
                for c in analysis["concerns"]:
                    print(f"   • {c}")

            if analysis["recommendations"]:
                print("\n💡 Recomendaciones:")
                for r in analysis["recommendations"]:
                    print(f"   • {r}")

            print("\n📦 Funciones sugeridas:")
            for func in analysis["suggested_functions"]:
                print(f"   • {func['name']} ({func['trigger']}): {func['description']}")

    elif args.command == "init":
        # Generar estructura básica
        functions = [
            {"name": "api", "trigger": "http"},
            {"name": "worker", "trigger": "sqs"},
        ]

        if args.framework == "serverless":
            output = generate_serverless_yml(args.name, functions)
        elif args.framework == "terraform":
            output = generate_terraform(args.name, "api")
        else:
            output = f"# Framework {args.framework} - Use SAM CLI to init"

    elif args.command == "function":
        output = generate_function(args.name, args.trigger, args.language)

    elif args.command == "cost":
        estimate = estimate_cost(args.invocations, args.duration, args.memory)

        if args.json:
            output = json.dumps(
                {
                    "invocations_per_month": estimate.invocations_per_month,
                    "avg_duration_ms": estimate.avg_duration_ms,
                    "memory_mb": estimate.memory_mb,
                    "requests_cost_usd": estimate.requests_cost,
                    "compute_cost_usd": estimate.compute_cost,
                    "total_monthly_usd": estimate.total_monthly,
                },
                indent=2,
            )
        else:
            print(f"\n{'=' * 60}")
            print(" ESTIMACIÓN DE COSTOS AWS LAMBDA")
            print(f"{'=' * 60}")
            print("\n📊 Parámetros:")
            print(f"   Invocaciones/mes: {estimate.invocations_per_month:,}")
            print(f"   Duración promedio: {estimate.avg_duration_ms}ms")
            print(f"   Memoria: {estimate.memory_mb}MB")
            print("\n💰 Costos (USD/mes):")
            print(f"   Requests: ${estimate.requests_cost:.2f}")
            print(f"   Compute: ${estimate.compute_cost:.2f}")
            print("   ─────────────────")
            print(f"   TOTAL: ${estimate.total_monthly:.2f}")

            if estimate.total_monthly == 0:
                print("\n✨ Dentro del free tier!")

    elif args.command == "iac":
        functions = [{"name": "api", "trigger": "http"}]

        if args.format == "serverless":
            output = generate_serverless_yml(args.name, functions)
        elif args.format == "terraform":
            output = generate_terraform(args.name, "api")
        else:
            output = "# Use SAM CLI: sam init"

    elif args.command == "triggers":
        if args.json:
            output = json.dumps(TRIGGERS, indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" TRIGGERS DISPONIBLES")
            print(f"{'=' * 60}\n")
            for trigger, desc in TRIGGERS.items():
                print(f"   {trigger:<15} {desc}")

    # Output
    if output:
        if hasattr(args, "output") and args.output:
            Path(args.output).write_text(output)
            print(f"✓ Escrito en {args.output}")
        else:
            print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
