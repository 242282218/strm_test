from app.services.scoring.tags import TagExtractor


def test_extract_returns_empty_set_when_no_patterns_match() -> None:
    extractor = TagExtractor()
    tags = extractor.extract("Interstellar 2014 release")
    assert tags == set()


def test_extract_matches_resolution_codec_and_container_tags() -> None:
    extractor = TagExtractor()

    tags = extractor.extract("Interstellar.2014.2160P.HEVC.REMUX")

    assert {"4k", "x265", "remux"} <= tags


def test_extract_matches_chinese_audio_subtitle_and_bluray_tags() -> None:
    extractor = TagExtractor()

    tags = extractor.extract("星际穿越 蓝光 原盘 杜比全景声 国英双语 中文字幕")

    assert {"bluray", "atmos", "multi_audio", "cn_sub"} <= tags


def test_extract_matches_symbol_variants_for_audio_and_hdr() -> None:
    extractor = TagExtractor()

    tags = extractor.extract("Movie WEB-DL HDR10+ DTS-X True-HD E-AC-3")

    assert {"webdl", "hdr", "dtsx", "truehd", "ddp"} <= tags
