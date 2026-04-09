# GFL2 Dishes Library

Static fan-site for the **Girls' Frontline 2: Exilium** lobby cooking mini-game.
Browse all 55 unique dishes, every recipe combination, both buff tiers, and alt-effects. UI is bilingual (EN / RU).

## Project layout

```
site/
├── index.html
├── assets/
│   ├── css/style.css
│   ├── js/app.js
│   ├── js/i18n.js
│   └── sprites/                # 55 dish icons (Lobby_Buff_Cook_21..75.png)
├── data/dishes.json            # generated
└── tools/build_data.py         # CSV → JSON + sprite copy
```

## Regenerating data

If `LobbyCookWildcardLookup.csv` is updated, run from the **repository root**:

```sh
python site/tools/build_data.py
```

The script:
1. Parses the CSV (handles multi-line quoted fields).
2. Maps each unique `results` name to a sprite by first appearance, starting at `Lobby_Buff_Cook_21.png`.
3. Splits `buff_description` and `alt_effect` on ` | ` into Lv1 / Lv2.
4. Converts `<color=#hex>…</color>` Unity tags to `<span class="hl" style="color:#hex">`.
5. Groups identical alt-effect templates (ignoring numeric/color differences) into `alt_NN` ids.
6. Writes `site/data/dishes.json` and copies sprites into `site/assets/sprites/`.

The script asserts there are exactly 55 unique dishes and that the sum of recipe counts equals the original row count (currently 275).

## Local preview

Open it via a simple HTTP server (the page uses `fetch()` for `dishes.json`, which won't work over `file://`):

```sh
cd site
python -m http.server 8000
# then open http://localhost:8000
```

## Deploying to GitHub Pages

The `site/` folder is fully static. Two options:

**Option A — push the folder as the entire repo root**
1. Copy contents of `site/` into the root of a new GitHub repo.
2. In the repo settings → *Pages* → set source to `main` branch / `/ (root)`.

**Option B — keep the existing repo, deploy `/site` subfolder**
1. Push this repo to GitHub.
2. In *Pages* → set source to `main` branch / `/site` folder.

No build step is needed.

## Data source

`LobbyCookWildcardLookup.csv` columns:

| column | meaning |
|---|---|
| `id` | recipe id (multiple recipes can produce the same dish) |
| `ingredients` | three ingredients separated by ` | ` |
| `results` | dish name (= sprite key) |
| `alt_effect` | alternative buff text (may be empty); ` | ` separates Lv1 / Lv2 |
| `buff_description` | main buff text; ` | ` separates Lv1 / Lv2 |
| `food_type_label` | category — one of 5 values |

Buff/alt-effect texts are not translated — they are pulled verbatim from the game.
