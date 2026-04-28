from lxml import etree

from app.services.tmdb_service import TMDBEpisode, TMDBMovieDetail, TMDBTVDetail


class NFOGenerator:
    """NFO生成器 (兼容Kodi/Emby)"""

    @staticmethod
    def generate_movie_nfo(movie: TMDBMovieDetail) -> str:
        """生成电影NFO"""
        root = etree.Element("movie")

        # Basic Info
        etree.SubElement(root, "title").text = movie.title
        etree.SubElement(root, "originaltitle").text = movie.original_title or ""
        etree.SubElement(root, "sorttitle").text = movie.title

        if movie.release_date:
            etree.SubElement(root, "year").text = movie.release_date[:4]
            etree.SubElement(root, "releasedate").text = movie.release_date

        if movie.runtime:
            etree.SubElement(root, "runtime").text = str(movie.runtime)

        etree.SubElement(root, "plot").text = movie.overview or ""

        if movie.vote_average:
            etree.SubElement(root, "rating").text = str(movie.vote_average)
        if movie.vote_count:
            etree.SubElement(root, "votes").text = str(movie.vote_count)

        if movie.id:
            uniqueid = etree.SubElement(root, "uniqueid", type="tmdb", default="true")
            uniqueid.text = str(movie.id)
            etree.SubElement(root, "tmdbid").text = str(movie.id)

        if movie.imdb_id:
            uniqueid = etree.SubElement(root, "uniqueid", type="imdb")
            uniqueid.text = movie.imdb_id
            etree.SubElement(root, "imdbid").text = movie.imdb_id

        # Genres
        if movie.genres:
            for genre in movie.genres:
                etree.SubElement(root, "genre").text = genre.name

        return etree.tostring(root, pretty_print=True, encoding="UTF-8", xml_declaration=True).decode("utf-8")

    @staticmethod
    def generate_tvshow_nfo(show: TMDBTVDetail) -> str:
        """生成电视剧NFO"""
        root = etree.Element("tvshow")

        etree.SubElement(root, "title").text = show.name
        etree.SubElement(root, "originaltitle").text = show.original_name or ""
        etree.SubElement(root, "sorttitle").text = show.name

        if show.first_air_date:
            etree.SubElement(root, "year").text = show.first_air_date[:4]
            etree.SubElement(root, "premiered").text = show.first_air_date

        etree.SubElement(root, "plot").text = show.overview or ""

        if show.vote_average:
            etree.SubElement(root, "rating").text = str(show.vote_average)
        if show.vote_count:
            etree.SubElement(root, "votes").text = str(show.vote_count)

        uniqueid = etree.SubElement(root, "uniqueid", type="tmdb", default="true")
        uniqueid.text = str(show.id)
        etree.SubElement(root, "tmdbid").text = str(show.id)

        etree.SubElement(root, "season").text = str(show.number_of_seasons)
        etree.SubElement(root, "episode").text = str(show.number_of_episodes)

        if show.genres:
            for genre in show.genres:
                etree.SubElement(root, "genre").text = genre.name

        return etree.tostring(root, pretty_print=True, encoding="UTF-8", xml_declaration=True).decode("utf-8")

    @staticmethod
    def generate_episode_nfo(episode: TMDBEpisode) -> str:
        """生成分集NFO"""
        root = etree.Element("episodedetails")

        etree.SubElement(root, "title").text = episode.name
        etree.SubElement(root, "season").text = str(episode.season_number)
        etree.SubElement(root, "episode").text = str(episode.episode_number)

        if episode.air_date:
            etree.SubElement(root, "aired").text = episode.air_date

        etree.SubElement(root, "plot").text = episode.overview or ""

        if episode.vote_average:
            etree.SubElement(root, "rating").text = str(episode.vote_average)

        uniqueid = etree.SubElement(root, "uniqueid", type="tmdb", default="true")
        uniqueid.text = str(episode.id)

        return etree.tostring(root, pretty_print=True, encoding="UTF-8", xml_declaration=True).decode("utf-8")
