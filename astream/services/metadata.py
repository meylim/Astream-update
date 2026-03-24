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


# ===========================
# Classe MetadataService
# ===========================
class MetadataService:
    """
    Service responsable de la gestion des métadonnées d'anime.
    Gère la récupération des détails, la construction des listes de vidéos,
    et l'enrichissement TMDB des métadonnées.
    """

    def __init__(self):
        self.animesama_api = animesama_api
        self.tmdb_service = tmdb_service

    async def get_complete_anime_meta(self, anime_id: str, config, request, b64config: str) -> Dict[str, Any]:
        """
        Récupère les métadonnées complètes de l'anime.
        Gère la récupération des détails, la construction des listes de vidéos,
        et l'enrichissement TMDB des métadonnées.
        """
        logger.info(f"META - Demande de métadonnées pour: {anime_id}")

        # PHASE 2 : Traduction de l'ID universel
        anime_slug = await id_mapper.translate_to_animesama_slug(anime_id)
        if not anime_slug:
            logger.error(f"META - Impossible de traduire l'ID ou de trouver le slug pour: {anime_id}")
            return {}

        logger.info(f"META - Slug traduit avec succès : {anime_slug}")

        try:
            # Récupération des détails complets (avec cache)
            enhanced_anime_data = await get_or_fetch_anime_details(self.animesama_api.details, anime_slug)

            if not enhanced_anime_data:
                logger.warning(f"META - Impossible de récupérer les détails pour {anime_slug}")
                return {}

            # Construction de la base des métadonnées
            meta = {
                "id": anime_id,  # On garde l'ID original demandé par Stremio
                "type": "anime",
                "name": enhanced_anime_data.get('title', anime_slug.replace('-', ' ').title()),
                "poster": enhanced_anime_data.get('poster_url') or enhanced_anime_data.get('cover_url'),
                "background": enhanced_anime_data.get('cover_url') or enhanced_anime_data.get('poster_url'),
                "description": enhanced_anime_data.get('synopsis', 'Aucun synopsis disponible.'),
                "genres": [],
                "links": [],
                "videos": []
            }

            # Enrichissement TMDB si activé (au niveau global et utilisateur)
            if settings.TMDB_ENABLED and config.tmdbEnabled:
                logger.info(f"META - Enrichissement TMDB activé pour {anime_slug}")
                tmdb_data = await self.tmdb_service.enrich_anime_meta(enhanced_anime_data)
                if tmdb_data:
                    if tmdb_data.get('poster'):
                        meta['poster'] = tmdb_data['poster']
                    if tmdb_data.get('background'):
                        meta['background'] = tmdb_data['background']
                    if tmdb_data.get('logo'):
                        meta['logo'] = tmdb_data['logo']
                    if tmdb_data.get('description'):
                        meta['description'] = tmdb_data['description']
                    if tmdb_data.get('genres') and not meta.get('genres'):
                        meta['genres'] = tmdb_data['genres']
                    if tmdb_data.get('runtime'):
                        meta['runtime'] = tmdb_data['runtime']
                    if tmdb_data.get('releaseInfo'):
                        meta['releaseInfo'] = tmdb_data['releaseInfo']
                    if tmdb_data.get('imdbRating'):
                        meta['imdbRating'] = tmdb_data['imdbRating']

            # Formatage des genres et liens
            genres_raw = enhanced_anime_data.get('genres', '')
            genres = parse_genres_string(genres_raw) if isinstance(genres_raw, str) else genres_raw

            if genres:
                meta['genres'] = genres
                meta["links"].extend(StremioLinkBuilder.build_genre_links(request, b64config, genres))

            if enhanced_anime_data.get('imdb_id'):
                meta["links"].extend(StremioLinkBuilder.build_imdb_link(enhanced_anime_data))

            # Construction de la liste des vidéos (saisons/épisodes)
            seasons = enhanced_anime_data.get("seasons", [])
            tmdb_mapping_enabled = settings.TMDB_ENABLED and config.tmdbEnabled and config.tmdbEpisodeMapping

            # Pré-récupération du mapping TMDB si nécessaire
            final_tmdb_map = {}
            if tmdb_mapping_enabled:
                logger.info(f"META - Mapping des épisodes TMDB activé pour {anime_slug}")
                final_tmdb_map = await self.tmdb_service.get_tmdb_episode_mapping(enhanced_anime_data)

            for season_data in seasons:
                season_number = season_data.get("season_number", 1)
                season_name = season_data.get("season_name", f"Saison {season_number}")
                episodes = season_data.get("episodes", [])

                for ep in episodes:
                    try:
                        # Gestion des différents formats d'épisodes
                        if isinstance(ep, dict):
                            episode_num = int(str(ep.get("episode_number", ep.get("number", 1))).split('-')[0])
                        else:
                            episode_num = int(str(ep).split('-')[0])

                        # L'ID vidéo est au format Anime-Sama pour que stream.py s'y retrouve !
                        video_id = f"as:{anime_slug}:s{season_number}e{episode_num}"
                        
                        episode_title, episode_overview = self._get_base_episode_info(enhanced_anime_data, ep, season_name, episode_num)

                        video = {
                            "id": video_id,
                            "title": episode_title,
                            "season": season_number,
                            "episode": episode_num,
                            "overview": episode_overview
                        }

                        # Application du mapping TMDB pour l'épisode
                        if final_tmdb_map:
                            self._apply_tmdb_episode_metadata(video, final_tmdb_map, config, season_number, episode_num)

                        # Formattage final du titre (ajoute le suffixe VOSTFR/VF etc. si dispo)
                        if isinstance(ep, dict) and ep.get("title") and ep.get("title") != str(episode_num):
                             video["title"] = f"{video['title']} - {ep.get('title')}"

                        meta["videos"].append(video)

                    except ValueError:
                        logger.warning(f"Impossible de parser le numéro d'épisode: {ep}")
                        continue

            logger.info(f"META - Génération de {len(meta['videos'])} vidéos/épisodes pour {anime_slug}")
            return meta

        except Exception as e:
            logger.error(f"META - Erreur lors de la récupération des métadonnées pour {anime_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    def _get_base_episode_info(self, enhanced_anime_data: dict, ep: Any, season_name: str, episode_num: int) -> tuple[str, str]:
        """Extrait les informations de base de l'épisode depuis les données Anime-Sama."""
        episode_title = f"Épisode {episode_num}"
        episode_overview = ""

        if isinstance(ep, dict):
             episode_title = ep.get("title", f"Épisode {episode_num}")
             if "name" in ep and ep["name"]:
                 episode_title = ep["name"]
        
        # Le titre de base
        episode_title = f"{season_name} - {episode_title}" if season_name else episode_title

        # Synopsis
        if enhanced_anime_data.get('type') == SEASON_TYPE_FILM:
            episode_overview = enhanced_anime_data.get('synopsis', "Film")
        else:
            episode_overview = enhanced_anime_data.get('synopsis', f"Episode {episode_num} de {season_name}")

        return episode_title, episode_overview

    def _apply_tmdb_episode_metadata(self, video: dict, final_tmdb_map: dict, config,
                                     season_number: int, episode_num: int) -> bool:
        episode_key = f"s{season_number}e{episode_num}"

        if episode_key in final_tmdb_map:
            tmdb_episode = final_tmdb_map[episode_key]

            if config.tmdbEpisodeMapping and season_number > 0:
                enriched = False
                if tmdb_episode.get("still_path"):
                    temp_client = TMDBClient(None)
                    video['thumbnail'] = temp_client.get_episode_image_url(tmdb_episode["still_path"])
                    enriched = True

                if tmdb_episode.get("air_date"):
                    video['released'] = f"{tmdb_episode['air_date']}T00:00:00.000Z"
                    enriched = True

                if tmdb_episode.get("name"):
                    video['title'] = tmdb_episode["name"]
                    enriched = True

                if tmdb_episode.get("overview") and len(tmdb_episode["overview"].strip()) > 10:
                    video['overview'] = tmdb_episode["overview"]
                    enriched = True

                return enriched

        return False


# ===========================
# Instance Singleton Globale
# ===========================
metadata_service = MetadataService()
