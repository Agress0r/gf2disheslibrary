# GFL2 Dishes Library

Static fan-site for the **Girls' Frontline 2: Exilium** lobby cooking mini-game.
Browse all unique dishes, every recipe combination, normal and lucky/improved cooking results, and alt-effects. UI is bilingual (EN / RU).

Additional ingredient effects use a compact two-column grid (one column on phones).
Select an ingredient to read its full game description below the grid. Percentages
come from game text; the shared buff note appears once.

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
  tools/build_data.py       # preserved legacy generator
```

## Regenerating Data

The current full build uses local tools kept outside Git. Run from the repository root:

```sh
python update_build.py
python update_build.py --local
python update_build.py --check-only
```

The full build reads ten game tables, resolves effects separately for normal
(quality 4) and lucky/improved (quality 5) results, and generates the site in a
temporary directory before validation. Satiety, Affinity, Ashen Tales parameters
and ingredient bonus texts come from the game tables. No manual placeholder
values are needed. It joins sprites by game result ID and checks image files.

To regenerate from an already refreshed lookup, use
`python local_build/build_data.py`. See `local_build/README.md` on the maintainer's
machine for the detailed data mapping and checks. The old
`site/tools/build_data.py` and `placeholder_values.json` are preserved legacy
tools; use the commands above for current data.

## Local Preview

Open it via a simple HTTP server. The page uses `fetch()` for `dishes.json`, so `file://` will not work.

```sh
cd site
python -m http.server 8000
```

## Deploying To GitHub Pages

The `site/` folder is fully static. The included workflow deploys only the public site files and removes `site/tools` from the Pages artifact.

## Data Source

Local game-export files are intentionally ignored by `.gitignore`; the published site only needs generated `site/data/dishes.json` and copied assets.

`GF2DEC/LobbyCookWildcardLookup.recreated.json` rows use:

| field | meaning |
|---|---|
| `id` | recipe id; multiple recipes can produce the same dish |
| `ingredients` | ingredients separated by ` | ` |
| `results` | dish name |
| `alt_effect` | alternative buff text; ` | ` separates normal / improved |
| `buff_description` | main buff text; ` | ` separates normal / improved |
| `food_type_label` | category |
| `buff_type` | in-game buff key, when present |

Effect templates come from game localization and receive per-quality game values.
In `dishes.json`, `buff_tier1` / `alt_tier1` are the normal result and
`buff_tier2` / `alt_tier2` are the lucky/improved result. `result_id` is the game
item ID. Raw templates remain in the local detailed lookup.
