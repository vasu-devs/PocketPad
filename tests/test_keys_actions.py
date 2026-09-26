import pytest

from host import actions
from host.injector import FakeInjector
from host.keys import VK, is_known_key, normalize_key, parse_combo


def test_normalize_aliases():
    assert normalize_key(" Control ") == "ctrl"
    assert normalize_key("Escape") == "esc"
    assert normalize_key("windows") == "win"


def test_parse_combo():
    assert parse_combo("ctrl+alt+Delete") == ("ctrl", "alt", "delete")
    with pytest.raises(ValueError):
        parse_combo("")
    with pytest.raises(ValueError):
        parse_combo("ctrl+nope")
    with pytest.raises(ValueError):
        parse_combo("a+b+c+d+e+f")


def test_vk_table_sane():
    assert VK["a"] == 0x41 and VK["f12"] == 0x7B and VK["0"] == 0x30
    assert is_known_key("volumeup") and not is_known_key("")


def test_every_catalog_action_runs():
    inj = FakeInjector()
    for entry in actions.catalog():
        actions.resolve(entry["name"])(inj)
    # "none" must not inject anything; every other action must.
    inj2 = FakeInjector()
    actions.resolve("none")(inj2)
    assert inj2.calls == []
    assert len(inj.calls) >= len(actions.catalog()) - 1


def test_catalog_shape():
    cat = actions.catalog()
    assert {"name", "label"} <= set(cat[0])
    assert len({c["name"] for c in cat}) == len(cat)
