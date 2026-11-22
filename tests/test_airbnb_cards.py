"""The listing cards' public face (tools/airbnb_cards.load_links): each listing's cover picture, the newest Inside Airbnb
snapshot it appears in, and whether it was open to book there, from <date>_listings.csv.gz files.

    python -m pytest tests -q        (small made-up snapshots; no real data, no network)
"""
import gzip
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import airbnb_cards as ac  # noqa: E402

HEAD = "id,name,picture_url,has_availability,price\n"


def write_snapshot(folder, date, rows):
    with gzip.open(folder / f"{date}_listings.csv.gz", "wt", encoding="utf-8", newline="") as f:
        f.write(HEAD + "".join(f'{i},"Home {i}",{pic},{avail},$100\n' for i, pic, avail in rows))


@pytest.fixture
def raw(tmp_path):
    write_snapshot(tmp_path, "2025-03-19", [(1, "https://a0.muscache.com/pictures/old-1.jpg", "t"),
                                             (2, "https://a0.muscache.com/pictures/old-2.jpg", "t"),
                                             (3, "", "t")])
    write_snapshot(tmp_path, "2026-09-22", [(1, "https://a0.muscache.com/pictures/new-1.jpg", "f"),
                                             (3, "https://z1.muscache.cn/pictures/3.jpg", "t"),
                                             (4, "https://a0.muscache.com/pictures/4.jpg", "")])
    return tmp_path


def test_snapshots_are_listed_oldest_first(raw):
    _, snaps = ac.load_links(raw)
    assert snaps == ["2025-03-19", "2026-09-22"]


def test_the_newest_snapshot_a_listing_appears_in_wins(raw):
    links, _ = ac.load_links(raw)
    assert links.loc[1, "last"] == 1 and links.loc[1, "pic"] == "pictures/new-1.jpg" and links.loc[1, "avail"] == 0
    assert links.loc[2, "last"] == 0 and links.loc[2, "pic"] == "pictures/old-2.jpg" and links.loc[2, "avail"] == 1


def test_a_picture_on_airbnbs_host_is_stored_without_the_host_and_any_other_whole(raw):
    links, _ = ac.load_links(raw)
    assert links.loc[4, "pic"] == "pictures/4.jpg"
    assert links.loc[3, "pic"] == "https://z1.muscache.cn/pictures/3.jpg"


def test_a_blank_availability_flag_reads_as_not_open_and_a_blank_picture_gives_way_to_a_newer_one(raw):
    links, _ = ac.load_links(raw)
    assert links.loc[4, "avail"] == 0
    assert links.loc[3, "pic"] == "https://z1.muscache.cn/pictures/3.jpg"      # blank in March 2025, a picture by September 2026


def test_an_empty_folder_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        ac.load_links(tmp_path)
