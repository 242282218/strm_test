from __future__ import annotations

import xml.etree.ElementTree as ET

from app.services.nfo_generator import NFOGenerator
from app.services.tmdb_service import TMDBEpisode, TMDBGenre, TMDBMovieDetail, TMDBTVDetail


def _parse_xml(xml_content: str) -> ET.Element:
    return ET.fromstring(xml_content)


def test_generate_movie_nfo_with_full_fields() -> None:
    movie = TMDBMovieDetail(
        id=100,
        title="Movie Title",
        original_title="Original Movie Title",
        release_date="2024-01-02",
        overview="Movie overview",
        poster_path="/poster.jpg",
        backdrop_path="/backdrop.jpg",
        runtime=125,
        status="Released",
        genres=[TMDBGenre(id=1, name="Action"), TMDBGenre(id=2, name="Drama")],
        vote_average=8.2,
        vote_count=1200,
        imdb_id="tt1234567",
    )

    xml = NFOGenerator.generate_movie_nfo(movie)
    root = _parse_xml(xml)

    assert root.tag == "movie"
    assert root.findtext("title") == "Movie Title"
    assert root.findtext("originaltitle") == "Original Movie Title"
    assert root.findtext("year") == "2024"
    assert root.findtext("releasedate") == "2024-01-02"
    assert root.findtext("runtime") == "125"
    assert root.findtext("plot") == "Movie overview"
    assert root.findtext("rating") == "8.2"
    assert root.findtext("votes") == "1200"
    assert root.findtext("tmdbid") == "100"
    assert root.findtext("imdbid") == "tt1234567"
    assert [genre.text for genre in root.findall("genre")] == ["Action", "Drama"]

    unique_ids = root.findall("uniqueid")
    assert len(unique_ids) == 2
    assert unique_ids[0].attrib["type"] == "tmdb"
    assert unique_ids[0].attrib["default"] == "true"
    assert unique_ids[0].text == "100"
    assert unique_ids[1].attrib["type"] == "imdb"
    assert unique_ids[1].text == "tt1234567"


def test_generate_movie_nfo_skips_optional_fields_when_empty() -> None:
    movie = TMDBMovieDetail(
        id=101,
        title="Movie",
        original_title="",
        release_date=None,
        overview=None,
        poster_path=None,
        backdrop_path=None,
        runtime=None,
        status=None,
        genres=[],
        vote_average=None,
        vote_count=None,
        imdb_id=None,
    )

    xml = NFOGenerator.generate_movie_nfo(movie)
    root = _parse_xml(xml)

    assert root.find("year") is None
    assert root.find("releasedate") is None
    assert root.find("runtime") is None
    assert root.find("rating") is None
    assert root.find("votes") is None
    assert root.find("imdbid") is None
    assert root.findtext("plot") == ""
    assert root.findtext("tmdbid") == "101"


def test_generate_tvshow_nfo_with_full_fields() -> None:
    show = TMDBTVDetail(
        id=200,
        name="Show Name",
        original_name="Original Show Name",
        first_air_date="2023-05-06",
        overview="Show overview",
        poster_path="/show-poster.jpg",
        backdrop_path="/show-backdrop.jpg",
        number_of_seasons=3,
        number_of_episodes=24,
        status="Returning Series",
        genres=[TMDBGenre(id=5, name="Sci-Fi")],
        vote_average=7.9,
        vote_count=800,
    )

    xml = NFOGenerator.generate_tvshow_nfo(show)
    root = _parse_xml(xml)

    assert root.tag == "tvshow"
    assert root.findtext("title") == "Show Name"
    assert root.findtext("originaltitle") == "Original Show Name"
    assert root.findtext("year") == "2023"
    assert root.findtext("premiered") == "2023-05-06"
    assert root.findtext("plot") == "Show overview"
    assert root.findtext("rating") == "7.9"
    assert root.findtext("votes") == "800"
    assert root.findtext("tmdbid") == "200"
    assert root.findtext("season") == "3"
    assert root.findtext("episode") == "24"
    assert [genre.text for genre in root.findall("genre")] == ["Sci-Fi"]

    unique_id = root.find("uniqueid")
    assert unique_id is not None
    assert unique_id.attrib["type"] == "tmdb"
    assert unique_id.attrib["default"] == "true"
    assert unique_id.text == "200"


def test_generate_tvshow_nfo_skips_optional_rating_and_votes() -> None:
    show = TMDBTVDetail(
        id=201,
        name="Show",
        original_name="",
        first_air_date=None,
        overview=None,
        poster_path=None,
        backdrop_path=None,
        number_of_seasons=1,
        number_of_episodes=1,
        status=None,
        genres=[],
        vote_average=None,
        vote_count=None,
    )

    xml = NFOGenerator.generate_tvshow_nfo(show)
    root = _parse_xml(xml)

    assert root.find("year") is None
    assert root.find("premiered") is None
    assert root.find("rating") is None
    assert root.find("votes") is None
    assert root.findtext("plot") == ""
    assert root.findtext("season") == "1"
    assert root.findtext("episode") == "1"


def test_generate_episode_nfo_with_and_without_optional_fields() -> None:
    episode = TMDBEpisode(
        id=300,
        name="Episode Name",
        episode_number=7,
        season_number=2,
        air_date="2022-07-08",
        overview="Episode overview",
        still_path="/episode.jpg",
        vote_average=8.5,
    )
    xml = NFOGenerator.generate_episode_nfo(episode)
    root = _parse_xml(xml)

    assert root.tag == "episodedetails"
    assert root.findtext("title") == "Episode Name"
    assert root.findtext("season") == "2"
    assert root.findtext("episode") == "7"
    assert root.findtext("aired") == "2022-07-08"
    assert root.findtext("plot") == "Episode overview"
    assert root.findtext("rating") == "8.5"

    unique_id = root.find("uniqueid")
    assert unique_id is not None
    assert unique_id.attrib["type"] == "tmdb"
    assert unique_id.attrib["default"] == "true"
    assert unique_id.text == "300"

    no_optional = TMDBEpisode(
        id=301,
        name="Episode",
        episode_number=1,
        season_number=1,
        air_date=None,
        overview=None,
        still_path=None,
        vote_average=None,
    )
    root_no_optional = _parse_xml(NFOGenerator.generate_episode_nfo(no_optional))
    assert root_no_optional.find("aired") is None
    assert root_no_optional.find("rating") is None
    assert root_no_optional.findtext("plot") == ""
