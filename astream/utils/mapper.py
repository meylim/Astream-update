import httpx
import asyncio
import re
from typing import Optional
from astream.utils.logger import logger

class IDMapper:
    """
    Le Traducteur Universel (Phase 2 - Étape 3)
    Convertit les IDs IMDb (tt...) et Kitsu (kitsu...) en slugs Anime-Sama.
    """
    
    async def get_title_from_stremio_id(self, stremio_id: str) -> Optional[str]:
        """Interroge Kitsu ou Cinemeta pour obtenir le vrai titre de l'œuvre."""
        title = None
        async with httpx.AsyncClient() as client:
            try:
                # Si c'est un ID Kitsu
                if stremio_id.startswith("kitsu:"):
                    kitsu_id = stremio_id.split(":")[1]
                    res = await client.get(f"https://kitsu.io/api/edge/anime/{kitsu_id}", timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        title = data.get("data", {}).get("attributes", {}).get("canonicalTitle")
                
                # Si c'est un ID IMDb (Cinemeta)
                elif stremio_id.startswith("tt"):
                    imdb_id = stremio_id.split(":")[0]
                    # Essayer en tant que série d'abord (Cinemeta)
                    res = await client.get(f"https://v3-cinemeta.strem.io/meta/series/{imdb_id}.json", timeout=10)
                    data = res.json()
                    if data and data.get("meta"):
                        title = data["meta"].get("name")
                    else:
                        # Fallback en tant que film
                        res = await client.get(f"https://v3-cinemeta.strem.io/meta/movie/{imdb_id}.json", timeout=10)
                        data = res.json()
                        if data and data.get("meta"):
                            title = data["meta"].get("name")
            except Exception as e:
                logger.error(f"MAPPER - Erreur réseau Cinemeta/Kitsu pour {stremio_id}: {e}")
                
        return title

    async def translate_to_animesama_slug(self, stremio_id: str) -> str:
        """Convertit n'importe quel ID Stremio en slug compatible Anime-Sama"""
        from astream.services.catalog import catalog_service
        
        # Si c'est déjà un ID Anime-Sama interne, on extrait juste le slug
        if stremio_id.startswith("as:"):
            return stremio_id.replace("as:", "").split(":")[0]
        
        # 1. Obtenir le vrai titre via APIs externes
        title = await self.get_title_from_stremio_id(stremio_id)
        if not title:
            logger.warning(f"MAPPER - Impossible de trouver un titre pour {stremio_id}")
            return ""
        
        logger.log("MAPPER", f"Traduction: {stremio_id} -> '{title}'. Recherche du slug Anime-Sama...")
        
        # 2. Utiliser la recherche "Live" pour trouver le slug correspondant sur Anime-Sama
        try:
            results = await catalog_service.get_complete_catalog(
                request=None, b64config=None, search=title
            )
            
            if results and len(results) > 0:
                # On prend le premier résultat (le plus pertinent)
                best_match_id = results[0].get("id", "")
                if best_match_id.startswith("as:"):
                    slug = best_match_id.replace("as:", "")
                    logger.log("MAPPER", f"Succès: Slug trouvé via recherche -> {slug}")
                    return slug
        except Exception as e:
            logger.error(f"MAPPER - Erreur lors de la recherche du slug: {e}")
            
        # 3. Fallback de secours si la recherche échoue
        return self.slugify_title(title)

    def slugify_title(self, title: str) -> str:
        """Méthode de secours pour transformer manuellement un titre en slug."""
        title = title.lower()
        title = re.sub(r'[^a-z0-9\s-]', '', title)
        return re.sub(r'[\s-]+', '-', title).strip('-')

id_mapper = IDMapper()
