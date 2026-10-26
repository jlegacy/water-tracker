import main

def test_valid_color_icon_allowlist():
    for c in main.STYLE_COLORS: assert main.valid_color(c) == c
    for i in main.STYLE_ICONS: assert main.valid_icon(i) == i
    for bad in (None, "", "red", "purple", "#ff0000", 5, ["blue"], "BLUE", "star"):
        assert main.valid_color(bad) == "default"
        assert main.valid_icon(bad) == "initial"

def test_palette_excludes_sos_red_leader_purple_and_star():
    assert not {"red", "purple", "violet", "pink", "magenta"} & set(main.STYLE_COLORS)
    assert "star" not in main.STYLE_ICONS

def test_entry_defaults_for_old_riders():
    r = main.new_rider("Old", None)
    r.update(lat=1.0, lon=2.0)
    e = main.entry("x", r); assert (e["color"], e["icon"]) == ("default", "initial")
    r.pop("color"); r.pop("icon")
    e = main.entry("x", r); assert (e["color"], e["icon"]) == ("default", "initial")
    r2 = main.new_rider("N", None, color="sky", icon="pirate"); r2.update(lat=1.0, lon=2.0)
    assert (main.entry("y", r2)["color"], main.entry("y", r2)["icon"]) == ("sky", "pirate")
