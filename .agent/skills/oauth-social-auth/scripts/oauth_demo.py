#!/usr/bin/env python3
"""
OAuth & Social Authentication Demo

Este script demuestra patrones de OAuth 2.0 y login social incluyendo:
- Generación de URLs de autorización
- Intercambio de códigos por tokens
- Validación de tokens
- Refresh tokens
- PKCE flow

Uso:
    python oauth_demo.py --demo auth-flow
    python oauth_demo.py --demo pkce
    python oauth_demo.py --demo token-validation
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlencode, parse_qs, urlparse

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Provider(Enum):
    """Proveedores de OAuth."""

    GOOGLE = "google"
    GITHUB = "github"
    APPLE = "apple"
    MICROSOFT = "microsoft"


@dataclass
class OAuthConfig:
    """Configuración de proveedor OAuth."""

    provider: Provider
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    scopes: list[str]
    userinfo_url: str | None = None


@dataclass
class AuthorizationRequest:
    """Request de autorización."""

    url: str
    state: str
    code_verifier: str | None = None  # Para PKCE


@dataclass
class TokenResponse:
    """Respuesta de tokens."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str = ""

    @property
    def expires_at(self) -> datetime:
        return datetime.now() + timedelta(seconds=self.expires_in)


@dataclass
class UserInfo:
    """Información del usuario."""

    id: str
    email: str
    name: str
    picture: str | None = None
    email_verified: bool = False
    provider: Provider | None = None


# Configuraciones de ejemplo (PLACEHOLDERS - reemplazar con valores reales)
PROVIDER_CONFIGS = {
    Provider.GOOGLE: OAuthConfig(
        provider=Provider.GOOGLE,
        client_id="PLACEHOLDER_GOOGLE_CLIENT_ID",
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        redirect_uri="http://localhost:3000/auth/google/callback",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
        scopes=["openid", "email", "profile"],
    ),
    Provider.GITHUB: OAuthConfig(
        provider=Provider.GITHUB,
        client_id="PLACEHOLDER_GITHUB_CLIENT_ID",
        client_secret=os.environ.get("GITHUB_CLIENT_SECRET", ""),
        redirect_uri="http://localhost:3000/auth/github/callback",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        scopes=["read:user", "user:email"],
    ),
    Provider.MICROSOFT: OAuthConfig(
        provider=Provider.MICROSOFT,
        client_id="PLACEHOLDER_MICROSOFT_CLIENT_ID",
        client_secret=os.environ.get("MICROSOFT_CLIENT_SECRET", ""),
        redirect_uri="http://localhost:3000/auth/microsoft/callback",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_url="https://graph.microsoft.com/v1.0/me",
        scopes=["openid", "email", "profile", "User.Read"],
    ),
}


class PKCEHelper:
    """Helper para PKCE (Proof Key for Code Exchange)."""

    @staticmethod
    def generate_code_verifier() -> str:
        """Generar code_verifier (43-128 caracteres)."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        """Generar code_challenge (SHA256 del verifier)."""
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    @staticmethod
    def verify(verifier: str, challenge: str) -> bool:
        """Verificar que el verifier corresponde al challenge."""
        expected = PKCEHelper.generate_code_challenge(verifier)
        return secrets.compare_digest(expected, challenge)


class OAuthClient:
    """
    Cliente OAuth simplificado para demostración.

    En producción, usar librerías como:
    - Python: authlib, python-social-auth
    - Node.js: passport, next-auth
    """

    def __init__(self, config: OAuthConfig) -> None:
        self.config = config
        self._states: dict[str, dict] = {}  # state -> metadata
        logger.info(f"OAuthClient inicializado para {config.provider.value}")

    def generate_state(self, metadata: dict | None = None) -> str:
        """Generar state para CSRF protection."""
        state = secrets.token_urlsafe(32)
        self._states[state] = {"created_at": datetime.now(), "metadata": metadata or {}}
        return state

    def validate_state(self, state: str) -> dict | None:
        """Validar y consumir state."""
        if state not in self._states:
            return None

        state_data = self._states.pop(state)

        # Verificar expiración (5 minutos)
        if datetime.now() - state_data["created_at"] > timedelta(minutes=5):
            logger.warning(f"State expirado: {state[:8]}...")
            return None

        return state_data["metadata"]

    def get_authorization_url(
        self, use_pkce: bool = False, extra_params: dict | None = None
    ) -> AuthorizationRequest:
        """Generar URL de autorización."""
        state = self.generate_state()

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state,
        }

        code_verifier = None

        if use_pkce:
            code_verifier = PKCEHelper.generate_code_verifier()
            code_challenge = PKCEHelper.generate_code_challenge(code_verifier)
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        if extra_params:
            params.update(extra_params)

        url = f"{self.config.authorize_url}?{urlencode(params)}"

        logger.info(f"URL de autorización generada para {self.config.provider.value}")

        return AuthorizationRequest(url=url, state=state, code_verifier=code_verifier)

    def exchange_code(
        self, code: str, state: str, code_verifier: str | None = None
    ) -> TokenResponse | None:
        """
        Intercambiar código de autorización por tokens.

        Nota: Esta es una simulación. En producción,
        se haría una petición HTTP real al token endpoint.
        """
        # Validar state
        metadata = self.validate_state(state)
        if metadata is None:
            logger.error("State inválido o expirado")
            return None

        # Simular respuesta de tokens
        logger.info("Intercambiando código por tokens...")

        # En producción, aquí se haría:
        # response = requests.post(self.config.token_url, data={
        #     "grant_type": "authorization_code",
        #     "client_id": self.config.client_id,
        #     "client_secret": self.config.client_secret,
        #     "code": code,
        #     "redirect_uri": self.config.redirect_uri,
        #     "code_verifier": code_verifier,  # Si PKCE
        # })

        return TokenResponse(
            access_token=f"access_{secrets.token_urlsafe(32)}",
            refresh_token=f"refresh_{secrets.token_urlsafe(32)}",
            expires_in=3600,
            id_token=self._generate_mock_id_token()
            if self.config.provider == Provider.GOOGLE
            else None,
            scope=" ".join(self.config.scopes),
        )

    def refresh_access_token(self, refresh_token: str) -> TokenResponse | None:
        """Refrescar access token."""
        logger.info("Refrescando access token...")

        # Simulación de refresh
        return TokenResponse(
            access_token=f"access_{secrets.token_urlsafe(32)}",
            refresh_token=f"refresh_{secrets.token_urlsafe(32)}",  # Rotation
            expires_in=3600,
            scope=" ".join(self.config.scopes),
        )

    def get_user_info(self, access_token: str) -> UserInfo:
        """
        Obtener información del usuario.

        En producción, se haría una petición al userinfo endpoint.
        """
        logger.info("Obteniendo información del usuario...")

        # Simulación
        return UserInfo(
            id=f"user_{secrets.token_urlsafe(8)}",
            email="user@example.com",
            name="Usuario Demo",
            picture="https://example.com/avatar.jpg",
            email_verified=True,
            provider=self.config.provider,
        )

    def _generate_mock_id_token(self) -> str:
        """Generar ID token simulado (JWT)."""
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "iss": "https://accounts.google.com",
            "sub": f"user_{secrets.token_urlsafe(8)}",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Usuario Demo",
            "picture": "https://example.com/avatar.jpg",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }

        def b64_encode(data: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

        # Nota: Esta es una simulación, no un JWT real firmado
        return f"{b64_encode(header)}.{b64_encode(payload)}.fake_signature"


class TokenValidator:
    """Validador de tokens."""

    @staticmethod
    def decode_jwt_payload(token: str) -> dict | None:
        """Decodificar payload de JWT (sin validar firma)."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Añadir padding si es necesario
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload = base64.urlsafe_b64decode(payload_b64)
            return json.loads(payload)
        except Exception as e:
            logger.error(f"Error decodificando JWT: {e}")
            return None

    @staticmethod
    def is_token_expired(payload: dict) -> bool:
        """Verificar si el token ha expirado."""
        exp = payload.get("exp")
        if not exp:
            return True
        return time.time() > exp


def demo_auth_flow() -> None:
    """Demostrar flujo de autorización OAuth."""
    logger.info("=== Demo: Flujo de Autorización OAuth ===")

    client = OAuthClient(PROVIDER_CONFIGS[Provider.GOOGLE])

    print("\n1. Generando URL de autorización...")
    auth_request = client.get_authorization_url(
        extra_params={"prompt": "consent", "access_type": "offline"}
    )

    print(f"\n   URL: {auth_request.url[:80]}...")
    print(f"   State: {auth_request.state[:16]}...")

    print("\n2. Usuario autoriza en el navegador...")
    print("   [Simulando redirect con código de autorización]")

    # Simular callback
    mock_code = f"auth_code_{secrets.token_urlsafe(16)}"

    print("\n3. Intercambiando código por tokens...")
    tokens = client.exchange_code(mock_code, auth_request.state)

    if tokens:
        print(f"\n   ✓ Access Token: {tokens.access_token[:20]}...")
        print(f"   ✓ Refresh Token: {tokens.refresh_token[:20]}...")
        print(f"   ✓ Expira en: {tokens.expires_in} segundos")
        print(f"   ✓ Scopes: {tokens.scope}")

        if tokens.id_token:
            print("\n4. Decodificando ID Token...")
            payload = TokenValidator.decode_jwt_payload(tokens.id_token)
            if payload:
                print(f"   Email: {payload.get('email')}")
                print(f"   Nombre: {payload.get('name')}")
                print(f"   Verificado: {payload.get('email_verified')}")

        print("\n5. Obteniendo información del usuario...")
        user = client.get_user_info(tokens.access_token)
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Nombre: {user.name}")


def demo_pkce_flow() -> None:
    """Demostrar flujo PKCE para SPAs/Mobile."""
    logger.info("=== Demo: Flujo PKCE ===")

    print("\n1. Generando PKCE challenge...")

    verifier = PKCEHelper.generate_code_verifier()
    challenge = PKCEHelper.generate_code_challenge(verifier)

    print(f"\n   Code Verifier: {verifier[:40]}...")
    print(f"   Code Challenge: {challenge[:40]}...")
    print("   Método: S256 (SHA-256)")

    print("\n2. Generando URL de autorización con PKCE...")

    client = OAuthClient(PROVIDER_CONFIGS[Provider.GOOGLE])
    auth_request = client.get_authorization_url(use_pkce=True)

    # Parsear URL para mostrar parámetros
    parsed = urlparse(auth_request.url)
    params = parse_qs(parsed.query)

    print("\n   Parámetros adicionales:")
    print(f"   - code_challenge: {params.get('code_challenge', [''])[0][:30]}...")
    print("   - code_challenge_method: S256")

    print("\n3. Verificando PKCE...")
    is_valid = PKCEHelper.verify(auth_request.code_verifier, params["code_challenge"][0])
    print(f"   ✓ Verificación: {'VÁLIDA' if is_valid else 'INVÁLIDA'}")

    print("\n   Nota: En el intercambio de tokens, se envía el")
    print("   code_verifier original y el servidor verifica que")
    print("   SHA256(verifier) == challenge almacenado")


def demo_token_validation() -> None:
    """Demostrar validación de tokens."""
    logger.info("=== Demo: Validación de Tokens ===")

    # Token de ejemplo (simulado)
    mock_id_token = OAuthClient(PROVIDER_CONFIGS[Provider.GOOGLE])._generate_mock_id_token()

    print("\n1. Decodificando ID Token...")
    print(f"   Token: {mock_id_token[:50]}...")

    payload = TokenValidator.decode_jwt_payload(mock_id_token)

    if payload:
        print("\n2. Contenido del token:")
        for key, value in payload.items():
            if key in ("iat", "exp"):
                dt = datetime.fromtimestamp(value)
                print(f"   {key}: {value} ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                print(f"   {key}: {value}")

        print("\n3. Validaciones:")
        is_expired = TokenValidator.is_token_expired(payload)
        print(f"   ✓ Expirado: {'SÍ' if is_expired else 'NO'}")
        print(f"   ✓ Emisor: {payload.get('iss')}")
        print(f"   ✓ Email verificado: {payload.get('email_verified')}")

    print("\n   Nota: En producción, también se debe:")
    print("   - Verificar la firma con la clave pública del proveedor")
    print("   - Validar el audience (aud) = tu client_id")
    print("   - Validar el issuer (iss) = URL del proveedor")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="OAuth & Social Authentication Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python oauth_demo.py --demo auth-flow
    python oauth_demo.py --demo pkce
    python oauth_demo.py --demo token-validation
    python oauth_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["auth-flow", "pkce", "token-validation", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("      OAUTH & SOCIAL AUTH PATTERNS DEMO")
    print("=" * 60)

    if args.demo in ("auth-flow", "all"):
        demo_auth_flow()
        print()

    if args.demo in ("pkce", "all"):
        demo_pkce_flow()
        print()

    if args.demo in ("token-validation", "all"):
        demo_token_validation()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con NextAuth, Passport y proveedores reales.")
    print("=" * 60)


if __name__ == "__main__":
    main()
