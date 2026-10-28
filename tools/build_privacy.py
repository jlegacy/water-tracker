"""Regenerate water-tracker-app/www/privacy.html from PRIVACY.md (pip install markdown)."""
import pathlib, markdown
root = pathlib.Path(__file__).resolve().parent.parent
body = markdown.markdown((root / "PRIVACY.md").read_text(), extensions=["tables", "sane_lists"])
css = """body{margin:0;background:#0b1d33;font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;color:#1f2937;line-height:1.55}
main{max-width:760px;margin:0 auto;background:#fff;padding:28px 22px 40px;min-height:100vh;box-sizing:border-box}
h1{color:#0B1D51;font-size:26px;border-bottom:3px solid #0D9488;padding-bottom:8px;margin-top:0}
h2{color:#0B1D51;font-size:19px;margin-top:28px}a{color:#0D9488}
table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}
th{background:#0B1D51;color:#fff;text-align:left}th,td{border:1px solid #cbd5e1;padding:6px 8px;vertical-align:top}
tr:nth-child(even) td{background:#f0f9f8}"""
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ride Radar Privacy Policy</title><style>{css}</style></head><body><main>{body}</main></body></html>"""
(root / "water-tracker-app/www/privacy.html").write_text(html)
