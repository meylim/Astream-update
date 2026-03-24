import asyncio
from typing import List, Dict, Any, Optional

from astream.utils.logger import logger
from astream.scrapers.animesama.client import animesama_api
from astream.scrapers.animesama.helpers import parse_genres_string
from astream.serviceso.tmdb.service import tmdb_service
from astream.utils.stremio_helpers import StremioMetaBuilder, StremioLinkBuilder

class CatalogService:
    def __init__(self):
        self.animesama_api = animesama_api
        self.tmdb_service = tmdb_service

    async def get_complete_catalog(self, request, b64config: str, search: Optional[str] = None,
                                   genre: Optional[str] = None, config=None) -> List[Dict[str, Any]]:
        metas = []
        anime_data = []

        try:
            if search:
                logger.info(f"CATALOG - Recherche Live via scraper : '{search}'")
                # On utilise la méthode exacte détectée dans tes logs
                if hasattr(self.animesama_api, 'search_anime'):
                    anime_data = await self.animesama_api.search_anime(search)
                elif hasattr(self.animesama_api, 'search'):
                    anime_data = await self.animesama_api.search(search)
            else:
                logger.info("CATALOG - Chargement du catalogue général...")
                
                # S'il y a une méthode de catalogue sur l'API, on l'utilise
                if hasattr(self.animesama_api, 'get_catalogue'):
                    anime_data = await self.animesama_api.get_catalogue()
                else:
                    logger.info("CATALOG - Utilisation du dataset en mémoire.")
                    from astream.utils.data_loader import get_dataset_loader
                    loader = get_dataset_loader()
                    # On utilise la bonne propriété du loader
                    anime_data = loader.dataset if hasattr(loader, 'dataset') else []
                    
                    if not anime_data:
                         logger.warning("CATALOG - Le dataset local est vide (0 anime).")

        except Exception as e:
            logger.error(f"CATALOG - Erreur récupération live: {e}")
            return []

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
