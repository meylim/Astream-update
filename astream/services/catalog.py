import asyncio
from typing import List, Dict, Any, Optional

from astream.utils.logger import logger
from astream.scrapers.animesama.client import animesama_api
from astream.scrapers.animesama.helpers import parse_genres_string
from astream.services.tmdb.service import tmdb_service
from astream.services.metadata import metadata_service
from astream.utils.cache import cache_stats
from astream.utils.stremio_helpers import StremioMetaBuilder, StremioLinkBuilder
from astream.config.settings import settings


class CatalogService:
    """
    Service responsable de la gestion du catalogue.
    Désormais 100% dynamique : plus besoin de dataset.json vide.
    """

    def __init__(self):
        self.animesama_api = animesama_api
        self.tmdb_service = tmdb_service

    async def get_complete_catalog(self, request, b64config: str, search: Optional[str] = None,
                                   genre_filter: Optional[str] = None, config=None) -> List[Dict[str, Any]]:
        """
        Récupère le catalogue en direct (Recherche ou Catalogue complet).
        """
        metas = []
        anime_data = []

        try:
            if search:
                # RECHERCHE LIVE sur Anime-Sama (Phase 2 - Étape 4)
                logger.log("CATALOG", f"Recherche en direct sur Anime-Sama : '{search}'")
                anime_data = await self.animesama_api.search(search)
            else:
                # CATALOGUE GÉNÉRAL (Souvent basé sur les nouveautés ou le planning)
                logger.log("CATALOG", "Chargement du catalogue live...")
                anime_data = await self.animesama_api.get_catalogue()
                
        except Exception as e:
            logger.error(f"CATALOG - Erreur récupération live: {e}")
            return []

        for anime in anime_data:
            try:
                anime_slug = anime.get('slug', '')
                if not anime_slug: continue

                # Extraction propre des genres
                genres_raw = anime.get('genres', '')
                genres = parse_genres_string(genres_raw) if isinstance(genres_raw, str) else genres_raw

                # Filtrage par genre (si demandé par Stremio)
                if genre_filter and genre_filter not in genres:
                    continue

                # Construction de la fiche Stremio (Image, Titre, Synopsis)
                meta = StremioMetaBuilder.build_catalog_meta(anime, config)
                
                # Ajout des liens cliquables
                meta["links"] = StremioLinkBuilder.build_genre_links(request, b64config, genres)
                meta["genres"] = genres

                metas.append(meta)

            except Exception as e:
                logger.error(f"CATALOG - Erreur meta pour {anime.get('slug')}: {e}")
                continue

        logger.log("API", f"CATALOG - {len(metas)} résultats affichés")
        return metas

    async def extract_unique_genres(self) -> List[str]:
        """Extrait la liste des genres pour le menu déroulant du Manifeste."""
        # On pourrait scraper la page d'accueil ou utiliser une liste fixe robuste
        return ["Action", "Aventure", "Comédie", "Drame", "Fantaisie", "Isekai", "Romance", "Sci-Fi", "Seinen", "Shonen", "Tranche de vie"]

catalog_service = CatalogService()
