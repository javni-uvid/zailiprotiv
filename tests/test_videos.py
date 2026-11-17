from zailiprotiv import videos

PAGE = """<div align="left">
<p align="left" class="style4"><span lang="SR-CYRL-RS">Прва седница Народне скупштине Републике Србије у Петнаестом сазиву 17.11.2026. </span>(I)(<a href="https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111710.mp4" target="_blank">MP4 153MB</a> / <a href="https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111710.mpg">MPEG 1GB</a>)</p>
<p align="left" class="style4">&nbsp;</p>
<p align="left" class="style4">наставак Трећег ванредног заседања у Тринаестом сазиву 15.06.2023.(II) (<a href="http://217.26.67.44/filesnsrs/zasedanja/zas2023061510a.mp4" target="_blank">MP4 689MB</a>)</p>
<p align="left" class="style4">институт посланичких питања последњег четвртка у месецу 15.06.2023.(I) (<a href="http://217.26.67.44/filesnsrs/zasedanja/zas2023061511.mp4">MP4 9MB</a>)</p>
<p align="left" class="style4">наставак Трећег ванредног заседања у Тринаестом сазиву 15.06.2023.(I) (<a href="http://217.26.67.44/filesnsrs/zasedanja/zas2023061510.mp4" target="_blank">MP4 1163MB</a>)</p>
</div>"""


def test_parse_reads_day_part_and_title():
    found = videos.parse(PAGE)
    assert len(found) == 4
    first = found[0]
    assert first == {"date": "2026-11-17", "part": 1,
                     "title": "Прва седница Народне скупштине Републике Србије у Петнаестом сазиву",
                     "url": "https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111710.mp4"}


def test_old_addresses_move_to_the_https_host():
    urls = [e["url"] for e in videos.parse(PAGE)]
    assert all(u.startswith("https://arhiva.videonet.co.rs/filesnsrs/") for u in urls)


def test_by_day_orders_parts_within_each_title():
    days = videos.by_day(videos.parse(PAGE))
    assert list(days) == ["2023-06-15", "2026-11-17"]
    assert [(p["title"][:5], p["part"]) for p in days["2023-06-15"]] == [("инсти", 1), ("наста", 1), ("наста", 2)]


def test_a_sittings_days_get_their_recordings_grouped():
    from zailiprotiv.pages_lists import recorded
    days = videos.by_day(videos.parse(PAGE))
    rows = recorded(["2023-06-14", "2023-06-15"], days, lambda s: s)
    assert [d for d, _ in rows] == ["2023-06-15"]
    groups = rows[0][1]
    assert [g["title"][:5] for g in groups] == ["инсти", "наста"]
    assert [p["n"] for p in groups[1]["parts"]] == ["I", "II"]
