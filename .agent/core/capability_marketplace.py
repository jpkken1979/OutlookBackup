"""
Capability Marketplace — mercado de skills entre ecosistemas.

Permite compartir, descubrir y adquirir skills entre instancias
federadas de Antigravity:
  - Publish: publicar skills disponibles
  - Browse: explorar skills de otros nodos
  - Acquire: obtener una skill de un nodo remoto
  - Rate: calificar skills adquiridas
  - Trending: skills populares

Usage:
    market = CapabilityMarketplace(bus=bus)

    # Publicar skill
    market.publish(
        skill_name="security-scan",
        provider="node-alpha",
        domain="security",
        description="Deep security scanning",
        quality=0.92,
    )

    # Buscar skills
    results = market.search("security")

    # Adquirir
    market.acquire("security-scan", requester="node-beta")

    # Calificar
    market.rate("security-scan", rating=4.5, reviewer="node-beta")
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.capability_marketplace")

# ============================================================
# Constantes
# ============================================================
MAX_LISTINGS = 1000  # Máximo de listings
MAX_REVIEWS = 50  # Reviews por listing
MAX_ACQUISITIONS = 2000  # Historial de adquisiciones


# ============================================================
# Modelos
# ============================================================
@dataclass
class SkillListing:
    """Listing de una skill en el marketplace."""

    listing_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    skill_name: str = ""
    provider: str = ""  # node_id del proveedor
    domain: str = "general"
    description: str = ""
    quality: float = 0.5
    tags: list[str] = field(default_factory=list)
    acquisitions: int = 0
    avg_rating: float = 0.0
    total_ratings: int = 0
    published_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "skill_name": self.skill_name,
            "provider": self.provider,
            "domain": self.domain,
            "description": self.description,
            "quality": round(self.quality, 3),
            "tags": self.tags,
            "acquisitions": self.acquisitions,
            "avg_rating": round(self.avg_rating, 2),
            "total_ratings": self.total_ratings,
            "published_at": self.published_at,
        }


@dataclass
class Acquisition:
    """Registro de adquisición de skill."""

    acquisition_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    listing_id: str = ""
    skill_name: str = ""
    provider: str = ""
    requester: str = ""
    status: str = "pending"  # pending, completed, failed
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "acquisition_id": self.acquisition_id,
            "listing_id": self.listing_id,
            "skill_name": self.skill_name,
            "provider": self.provider,
            "requester": self.requester,
            "status": self.status,
            "timestamp": self.timestamp,
        }


@dataclass
class Review:
    """Calificación de una skill."""

    reviewer: str = ""
    rating: float = 3.0
    comment: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "rating": round(self.rating, 1),
            "comment": self.comment,
            "timestamp": self.timestamp,
        }


# ============================================================
# Capability Marketplace
# ============================================================
class CapabilityMarketplace:
    """
    Mercado de skills entre ecosistemas federados.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Listings por skill_name
        self._listings: dict[str, SkillListing] = {}

        # Reviews por listing_id
        self._reviews: dict[str, list[Review]] = defaultdict(list)

        # Historial de adquisiciones
        self._acquisitions: list[Acquisition] = []

        # Métricas
        self._metrics = {
            "skills_published": 0,
            "skills_acquired": 0,
            "reviews_submitted": 0,
            "searches_performed": 0,
        }

    # --------------------------------------------------------
    # Publish
    # --------------------------------------------------------
    def publish(
        self,
        skill_name: str,
        provider: str,
        domain: str = "general",
        description: str = "",
        quality: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Publica una skill en el marketplace."""
        if len(self._listings) >= MAX_LISTINGS:
            # Remover la más antigua sin adquisiciones
            stale = [l for l in self._listings.values() if l.acquisitions == 0]
            if stale:
                stale.sort(key=lambda l: l.published_at)
                del self._listings[stale[0].skill_name]

        listing = SkillListing(
            skill_name=skill_name,
            provider=provider,
            domain=domain,
            description=description,
            quality=max(0.0, min(1.0, quality)),
            tags=tags or [],
        )
        self._listings[skill_name] = listing
        self._metrics["skills_published"] += 1

        logger.info("Skill published: %s by %s", skill_name, provider)
        return listing.to_dict()

    def unpublish(self, skill_name: str) -> bool:
        """Remueve una skill del marketplace."""
        if skill_name in self._listings:
            del self._listings[skill_name]
            return True
        return False

    # --------------------------------------------------------
    # Search & Browse
    # --------------------------------------------------------
    def search(
        self,
        query: str = "",
        domain: str | None = None,
        min_quality: float = 0.0,
        min_rating: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Busca skills en el marketplace."""
        self._metrics["searches_performed"] += 1
        q = query.lower()

        results = []
        for listing in self._listings.values():
            if q and q not in listing.skill_name.lower() and q not in listing.description.lower():
                if not any(q in t.lower() for t in listing.tags):
                    continue
            if domain and listing.domain != domain:
                continue
            if listing.quality < min_quality:
                continue
            if listing.avg_rating < min_rating:
                continue
            results.append(listing.to_dict())

        return sorted(results, key=lambda r: r["quality"], reverse=True)

    def browse(self, domain: str | None = None) -> list[dict[str, Any]]:
        """Navega el marketplace."""
        listings = list(self._listings.values())
        if domain:
            listings = [l for l in listings if l.domain == domain]
        return [
            l.to_dict()
            for l in sorted(
                listings,
                key=lambda l: l.acquisitions,
                reverse=True,
            )
        ]

    def get_listing(self, skill_name: str) -> dict[str, Any] | None:
        """Detalle de un listing."""
        listing = self._listings.get(skill_name)
        return listing.to_dict() if listing else None

    # --------------------------------------------------------
    # Acquire
    # --------------------------------------------------------
    def acquire(
        self,
        skill_name: str,
        requester: str,
    ) -> dict[str, Any]:
        """Adquiere una skill del marketplace."""
        listing = self._listings.get(skill_name)
        if not listing:
            return {"error": "Skill not found"}

        acquisition = Acquisition(
            listing_id=listing.listing_id,
            skill_name=skill_name,
            provider=listing.provider,
            requester=requester,
            status="completed",
        )
        listing.acquisitions += 1
        self._acquisitions.append(acquisition)

        if len(self._acquisitions) > MAX_ACQUISITIONS:
            self._acquisitions = self._acquisitions[-MAX_ACQUISITIONS:]

        self._metrics["skills_acquired"] += 1
        return acquisition.to_dict()

    # --------------------------------------------------------
    # Rate
    # --------------------------------------------------------
    def rate(
        self,
        skill_name: str,
        rating: float,
        reviewer: str,
        comment: str = "",
    ) -> dict[str, Any]:
        """Califica una skill."""
        listing = self._listings.get(skill_name)
        if not listing:
            return {"error": "Skill not found"}

        rating = max(1.0, min(5.0, rating))
        review = Review(reviewer=reviewer, rating=rating, comment=comment)

        reviews = self._reviews[listing.listing_id]
        reviews.append(review)
        if len(reviews) > MAX_REVIEWS:
            reviews.pop(0)

        # Recalcular promedio
        all_ratings = [r.rating for r in reviews]
        listing.avg_rating = sum(all_ratings) / len(all_ratings)
        listing.total_ratings = len(all_ratings)

        self._metrics["reviews_submitted"] += 1
        return {
            "skill_name": skill_name,
            "new_avg_rating": round(listing.avg_rating, 2),
            "total_ratings": listing.total_ratings,
        }

    def get_reviews(self, skill_name: str) -> list[dict[str, Any]]:
        """Reviews de una skill."""
        listing = self._listings.get(skill_name)
        if not listing:
            return []
        reviews = self._reviews.get(listing.listing_id, [])
        return [r.to_dict() for r in reviews][::-1]

    # --------------------------------------------------------
    # Trending
    # --------------------------------------------------------
    def trending(self, limit: int = 10) -> list[dict[str, Any]]:
        """Skills trending (más adquiridas recientemente)."""
        listings = sorted(
            self._listings.values(),
            key=lambda l: l.acquisitions,
            reverse=True,
        )
        return [l.to_dict() for l in listings[:limit]]

    def top_rated(self, limit: int = 10) -> list[dict[str, Any]]:
        """Skills mejor calificadas."""
        rated = [l for l in self._listings.values() if l.total_ratings > 0]
        rated.sort(key=lambda l: l.avg_rating, reverse=True)
        return [l.to_dict() for l in rated[:limit]]

    def get_domains(self) -> list[dict[str, int]]:
        """Dominios disponibles con conteo."""
        domain_counts: dict[str, int] = defaultdict(int)
        for listing in self._listings.values():
            domain_counts[listing.domain] += 1
        return [
            {"domain": d, "count": c}  # type: ignore[dict-item]  # return type broader than annotation
            for d, c in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del marketplace."""
        return {
            "total_listings": len(self._listings),
            "total_acquisitions": len(self._acquisitions),
            "domains": len({l.domain for l in self._listings.values()}),
            "providers": len({l.provider for l in self._listings.values()}),
            "metrics": {**self._metrics},
        }


# ============================================================
# Singleton
# ============================================================
_instance: CapabilityMarketplace | None = None


def get_capability_marketplace(bus: Any = None) -> CapabilityMarketplace:
    """Obtiene o crea el marketplace global."""
    global _instance
    if _instance is None:
        _instance = CapabilityMarketplace(bus=bus)
    return _instance
