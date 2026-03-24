import asyncio
from typing import Dict, Any, Optional, TYPE_CHECKING

from astream.utils.logger import logger
from astream.scrapers.animesama.client import animesama_api
from astream.scrapers.animesama.player import animesama_player
from astream.scrapers.animesama.details import get_or_fetch_anime_details
from astream.services.tmdb.service import tmdb_service
from astream.services.tmdb.client import TMDBClient
from astream.config.settings import settings, SEASON_TYPE_FILM
from astream.scrapers.animesama.helpers import parse_genres_string
from astream.utils.stremio_helpers import StremioMetaBuilder, StremioLinkBuilder
from astream.utils.mapper import id_mapper

if TYPE_CHECKING:
    from astream.scrapers.animesama.player import AnimeSamaPlayer
    from astream.scrapers.animesama.client import AnimeSamaAPI


class MetadataService:
    """
    Service responsable de la gestion des métadonnées d'anime.
    Modifié pour supporter la traduction d'ID universelle (IMDb/Kitsu).
    """

    def __init__(self):
        self.animesama_api = animesama_api
        self.tmdb_service = tmdb_service

    async def get_complete_anime_meta(self, anime_id: str, config, request, b64config: str) -> Dict[str, Any]:
        """
        Récupère les métadonnées complètes.
        Traduit l'ID IMDb/Kitsu en slug Anime-Sama avant de chercher.
        """
        # Phase 2 - Traduction
        anime_slug = await id_mapper.translate_to_animesama_slug(anime_id)
        if not anime_slug:
            logger.error(f"META - Échec traduction pour {anime_id}")
            return {}

        logger.log("META", f"Chargement métadonnées pour: {anime_slug} (Original: {anime_id})")
        
        # On travaille désormais avec l'ID interne pour Anime-Sama
        internal_id = f"as:{anime_slug}"

        try:
            # Récupération des détails depuis Anime-Sama (Scraping ou Cache)
            anime_data = await get_or_fetch_anime_details(self.animesama_api.details, anime_slug)
            if not anime_data:
                return {}

            # Construction de la meta de base enrichie avec TMDB
            meta = await StremioMetaBuilder.build_metadata_full(
                anime_data, 
                config, 
                self.tmdb_service, 
                internal_id
            )

            # Ajout des liens (genres, IMDb etc)
            genres_raw = anime_data.get('genres', '')
            genres = parse_genres_string(genres_raw) if isinstance(genres_raw, str) else genres_raw
            
            meta["links"] = StremioLinkBuilder.build_genre_links(request, b64config, genres)
            if anime_data.get('imdb_id'):
                meta["links"] += StremioLinkBuilder.build_imdb_link(anime_data)

            return meta

        except Exception as e:
            logger.error(f"META - Erreur récupération: {e}")
            return {}

metadata_service = MetadataService()
