from typing import List, Optional, Dict, Any
import asyncio

from astream.utils.logger import logger
from astream.scrapers.animesama.client import animesama_api
from astream.scrapers.animesama.player import animesama_player
from astream.utils.http_client import http_client
from astream.utils.parsers import MediaIdParser
from astream.scrapers.animesama.details import get_or_fetch_anime_details
from astream.scrapers.animesama.video_resolver import AnimeSamaVideoResolver
from astream.utils.data_loader import get_dataset_loader
from astream.utils.cache import CacheManager
from astream.config.settings import settings
from astream.utils.languages import filter_by_language, sort_by_language_priority
from astream.utils.stremio_helpers import format_stream_for_stremio
from astream.utils.mapper import id_mapper

class StreamService:
    def __init__(self):
        pass

    async def get_episode_streams(self, episode_id: str, language_filter: Optional[str] = None, language_order: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        parts = episode_id.split(":")
        anime_slug = ""
        season, episode = 1, 1

        if episode_id.startswith("as:"):
            anime_slug = parts[1]
            try:
                ep_part = parts[2].lower()
                if 's' in ep_part and 'e' in ep_part:
                    season = int(ep_part.split('s')[1].split('e')[0])
                    episode = int(ep_part.split('e')[1])
                else:
                    episode = int(ep_part)
            except (IndexError, ValueError):
                pass
        elif episode_id.startswith("tt") or episode_id.startswith("kitsu"):
            base_id = f"{parts[0]}:{parts[1]}" if episode_id.startswith("kitsu") else parts[0]
            anime_slug = await id_mapper.translate_to_animesama_slug(base_id)
            try:
                if episode_id.startswith("tt"):
                    season, episode = int(parts[1]), int(parts[2])
                else: 
                    episode = int(parts[2])
            except (IndexError, ValueError):
                pass

        if not anime_slug:
            logger.error(f"STREAM - Impossible d'identifier l'anime pour {episode_id}")
            return []

        logger.info(f"STREAM - Recherche de flux pour {anime_slug} S{season}E{episode}")

        try:
            anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)
            if not anime_data:
                return []

            seasons = anime_data.get("seasons", [])
            target_season = next((s for s in seasons if s.get("season_number") == season), None)

            if not target_season:
                logger.warning(f"STREAM - Saison {season} introuvable pour {anime_slug}")
                return []

            player_urls = await animesama_player.extractor.extract_player_urls_smart_mapping_with_language(
                anime_slug=anime_slug,
                season_data=target_season,
                episode_number=episode,
                language_filter=language_filter,
                config=config
            )

            return player_urls

        except Exception as e:
            logger.error(f"STREAM - Erreur scraping: {e}")
            return []

stream_service = StreamService()
