# GFL2 Dishes Library

Static fan-site for the **Girls' Frontline 2: Exilium** lobby cooking mini-game.
Browse all 56 unique dishes, every recipe combination, both buff tiers, and alt-effects. UI is bilingual (EN / RU).

## Project Layout

```text
site/
  index.html
  assets/
    css/style.css
    js/app.js
    js/i18n.js
    ingredients/            # generated ingredient icons
    sprites/                # 56 dish icons (Lobby_Buff_Cook_21..76.png)
  data/dishes.json          # generated site data
  tools/build_data.py       # local game data -> site JSON + asset copy
```

## Regenerating Data

The build script prefers `LobbyCookWildcardLookup.json`. If it is not present,
it falls back to `LobbyCookWildcardLookup.csv`.

Run from the repository root:

```sh
python site/tools/build_data.py
```

The script:

1. Loads recipe rows from `LobbyCookWildcardLookup.json`.
2. Loads sprite mapping from `LobbyCookIllustrationsData.decoded.json`, falling back to `LobbyCookIllustrationsData.json`.
3. Maps each unique dish to the matching illustration entry by the canonical 2-ingredient recipes.
4. Splits `buff_description` and `alt_effect` on ` | ` into Lv1 / Lv2.
5. Converts Unity `<color=#hex>...</color>` tags to HTML spans.
6. Writes `site/data/dishes.json`.
7. Copies dish sprites and ingredient icons into `site/assets/`.

Current sanity checks expect 289 total recipes, 56 unique dishes, and 56 copied dish sprites.

## Local Preview

Open it via a simple HTTP server. The page uses `fetch()` for `dishes.json`, so `file://` will not work.

```sh
cd site
python -m http.server 8000
# then open http://localhost:8000
```

From the repository root you can also use `Launch.bat`.

## Deploying To GitHub Pages

The `site/` folder is fully static. The included workflow deploys only the public site files and removes `site/tools` from the Pages artifact.

## Data Source

Local game-export files are intentionally ignored by `.gitignore`; the published site only needs generated `site/data/dishes.json` and copied assets.

`LobbyCookWildcardLookup.json` rows use:

| field | meaning |
|---|---|
| `id` | recipe id; multiple recipes can produce the same dish |
| `ingredients` | ingredients separated by ` | ` |
| `results` | dish name |
| `alt_effect` | alternative buff text; ` | ` separates Lv1 / Lv2 |
| `buff_description` | main buff text; ` | ` separates Lv1 / Lv2 |
| `food_type_label` | category |
| `buff_type` | in-game buff key, when present |

Buff and alt-effect texts are pulled verbatim from the game.
