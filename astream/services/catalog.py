import asyncio
from typing import List, Dict, Any, Optional

from astream.utils.logger import logger
from astream.scrapers.animesama.client import animesama_api
from astream.scrapers.animesama.helpers import parse_genres_string
from astream.services.tmdb.service import tmdb_service
from astream.utils.stremio_helpers import StremioMetaBuilder, StremioLinkBuilder


class CatalogService:
    """
    Service responsable de la gestion du catalogue.
    Ultra-Sécurisé : Détecte dynamiquement les méthodes du scraper pour éviter tout crash.
    """

    def __init__(self):
        self.animesama_api = animesama_api
        self.tmdb_service = tmdb_service

    async def get_complete_catalog(self, request, b64config: str, search: Optional[str] = None,
                                   genre: Optional[str] = None, config=None) -> List[Dict[str, Any]]:
        metas = []
        anime_data = []

        try:
            # --- 1. INTROSPECTION DYNAMIQUE DU SCRAPER ---
            # On cherche intelligemment la méthode de recherche, peu importe son nom
            search_fetcher = getattr(self.animesama_api, 'search', None)
            if not search_fetcher:
                search_fetcher = getattr(self.animesama_api, 'search_anime', None)

            # On cherche intelligemment la méthode pour avoir le catalogue entier
            catalog_fetcher = getattr(self.animesama_api, 'get_catalogue', None)
            if not catalog_fetcher:
                catalog_fetcher = getattr(self.animesama_api, 'get_catalog', None)
            if not catalog_fetcher:
                catalog_fetcher = getattr(self.animesama_api, 'get_all', None)
                
            # Parfois, c'est rangé dans un sous-module (ex: animesama_api.catalog.get_all)
            if not catalog_fetcher and hasattr(self.animesama_api, 'catalog'):
                catalog_fetcher = getattr(self.animesama_api.catalog, 'get_all', None)
                if not catalog_fetcher:
                    catalog_fetcher = getattr(self.animesama_api.catalog, 'get_catalogue', None)

            # --- 2. RÉCUPÉRATION DES DONNÉES ---
            if search and search_fetcher:
                logger.info(f"CATALOG - Recherche Live via scraper : '{search}'")
                anime_data = await search_fetcher(search)
                
            elif catalog_fetcher:
                logger.info("CATALOG - Chargement via le scraper interne...")
                full_catalog = await catalog_fetcher()
                
                if search:
                    search_lower = search.lower()
                    anime_data = [a for a in full_catalog if search_lower in a.get('title', '').lower() or search_lower in a.get('slug', '').lower()]
                else:
                    anime_data = full_catalog
                    
            else:
                # Si AUCUNE méthode n'est trouvée, on log les méthodes disponibles pour débugger
                api_methods = [m for m in dir(self.animesama_api) if not m.startswith('_')]
                logger.error(f"CATALOG - Scraper incomplet ! Méthodes trouvées dans client.py: {api_methods}")
                logger.warning("CATALOG - Fallback sur le dataset local (qui est peut-être vide).")
                
                from astream.utils.data_loader import get_dataset_loader
                full_catalog = await get_dataset_loader().get_all_animes()
                
                if search:
                    search_lower = search.lower()
                    anime_data = [a for a in full_catalog if search_lower in a.get('title', '').lower() or search_lower in a.get('slug', '').lower()]
                else:
                    anime_data = full_catalog

        except Exception as e:
            logger.error(f"CATALOG - Erreur récupération live: {e}")
            return []

        # --- 3. CONSTRUCTION DES FICHES ---
        for anime in anime_data:
            try:
                anime_slug = anime.get('slug', '')
                if not anime_slug: continue

                genres_raw = anime.get('genres', '')
                genres = parse_genres_string(genres_raw) if isinstance(genres_raw, str) else genres_raw

                if genre and genre not in genres:
                    continue

                meta = StremioMetaBuilder.build_catalog_meta(anime, config)
                meta["links"] = StremioLinkBuilder.build_genre_links(request, b64config, genres)
                meta["genres"] = genres

                metas.append(meta)

            except Exception as e:
                logger.error(f"CATALOG - Erreur meta pour {anime.get('slug', 'inconnu')}: {e}")
                continue

        logger.info(f"CATALOG - {len(metas)} résultats affichés")
        return metas

    async def extract_unique_genres(self) -> List[str]:
        return ["Action", "Aventure", "Comédie", "Drame", "Fantaisie", "Isekai", "Romance", "Sci-Fi", "Seinen", "Shonen", "Tranche de vie"]

catalog_service = CatalogService()
