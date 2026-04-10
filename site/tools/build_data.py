"""
Build site/data/dishes.json from LobbyCookWildcardLookup.csv
and copy sprites to site/assets/sprites/.

Run from repo root:
    python site/tools/build_data.py
"""
import csv
import json
import os
import re
import shutil
import sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
CSV_CANDIDATES = [
    os.path.join(ROOT, "LobbyCookWildcardLookup.csv"),
    r"e:\Загрузки\LobbyCookWildcardLookup.csv",
]
ILLUSTRATIONS_PATH = os.path.join(ROOT, "LobbyCookIllustrationsData.json")
SPRITES_SRC = os.path.join(ROOT, "DishesImages", "Sprite")
SPRITES_DST = os.path.join(SITE, "assets", "sprites")
INGREDIENTS_SRC = os.path.join(ROOT, "Ingredients", "Sprite")
INGREDIENTS_DST = os.path.join(SITE, "assets", "ingredients")
DATA_DST = os.path.join(SITE, "data", "dishes.json")

# CSV ids 221..275 are the 55 canonical 2-ingredient "wildcard pair" recipes
# (one per unique dish). They line up 1:1, in order, with entries in
# LobbyCookIllustrationsData.json (field_1 1741001..1741055), which is the
# authoritative source for sprite assignment via field_10.
PAIR_ID_FIRST = 221
PAIR_ID_LAST = 275

# Ingredient name -> source filename in Ingredients/Sprite/.
# Includes the misspelled "Greenhoues Bell Pepper.png" mapped to the
# correct in-game name.
INGREDIENT_FILES = {
    "Cheese": "Cheese.png",
    "Chill Pepper": "Chill Pepper.png",
    "Cilantro": "Cilantro.png",
    "Curry": "Curry.png",
    "Dried Shrimp": "Dried Shrimp.png",
    "Egg": "Egg.png",
    "Garlic": "Garlic.png",
    "Greenhouse Bell Pepper": "Greenhoues Bell Pepper.png",
    "Greenhouse Cucumber": "Greenhouse Cucumber.png",
    "Greenhouse Vegetables": "Greenhouse Vegetables.png",
    "Lemon": "Lemon.png",
    "Mushroom": "Mushroom.png",
    "Purple Sweet Potato": "Purple Sweet Potato.png",
    "Synthetic Fish": "Synthetic Fish.png",
    "Synthetic Meat": "Synthetic Meat.png",
    "Synthetic Poultry": "Synthetic Poultry.png",
    "Tofu": "Tofu.png",
    "Tomato": "Tomato.png",
    "Wheat": "Wheat.png",
    "White Rice": "White Rice.png",
}


def ingredient_icon_filename(name):
    """Normalized, URL-safe filename for an ingredient sprite."""
    return name.replace(" ", "_") + ".png"

COLOR_RE = re.compile(r"<color=(#[0-9a-fA-F]{6})>(.*?)</color>", re.DOTALL)

ACCENT = "#f26c1c"
HL_OPEN = f'<span class="hl" style="color:{ACCENT}">'
HL_CLOSE = "</span>"

# {0} placeholder appears in Long-term consumption / satiety texts;
# in-game value is always 4.
PLACEHOLDER_ZERO_VALUE = "4"

# Numbers wrapped in (parentheses) — e.g. "Duration: (180)s" — get highlighted.
PAREN_NUMBER_RE = re.compile(r"\((\d+(?:\.\d+)?)\)")

# Permanent bonuses awarded when a Dine In (General) dish is unlocked
# (cooked for the first time) via a 2-ingredient recipe — each of these
# 10 "extra" ingredients grants its own permanent buff.
DISH_UNLOCK_BONUSES = [
    ("Chill Pepper",  "Burn damage dealt is increased by <color=#f26c1c>3%</color>. This buff cannot be dispelled."),
    ("Dried Shrimp",  "Hydro damage dealt is increased by <color=#f26c1c>3%</color>. This buff cannot be dispelled."),
    ("Lemon",         "Electric damage dealt is increased by <color=#f26c1c>3%</color>. Buff cannot be dispelled."),
    ("Mushroom",      "Corrosion damage dealt is increased by <color=#f26c1c>3%</color>. Buff cannot be dispelled."),
    ("Egg",           "Freeze damage dealt is increased by <color=#f26c1c>3%</color>. Buff cannot be dispelled."),
    ("Garlic",        "Physical damage dealt is increased by <color=#f26c1c>3%</color>. Buff cannot be dispelled."),
    ("Cheese",        "DEF +<color=#f26c1c>1.5%</color>. Buff cannot be dispelled."),
    ("Curry",         "Max HP +<color=#f26c1c>1.5%</color>. Buff cannot be dispelled."),
    ("Cilantro",      "CRIT Rate and CRIT DMG +<color=#f26c1c>1%</color>. Buff cannot be dispelled."),
    ("Tofu",          "Attack increased by <color=#f26c1c>1.5%</color>. Buff cannot be dispelled."),
]


def find_csv():
    for p in CSV_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit(f"CSV not found in: {CSV_CANDIDATES}")


def normalize_html(text):
    """Convert Unity <color=#xxx>...</color> tags to <span class='hl'>.

    Also: returns None for empty/whitespace/bare-pipe input, highlights
    {0} placeholders (always = 4) and numbers inside (parentheses).
    """
    if text is None:
        return None
    text = text.strip()
    if not text or text == "|":
        return None
    # Substitute {0} placeholder with literal value BEFORE color-tag conversion,
    # so a wrapping <color>...{0}...</color> ends up as a single span (not nested).
    text = text.replace("{0}", PLACEHOLDER_ZERO_VALUE)
    # Replace color tags
    text = COLOR_RE.sub(
        lambda m: f'<span class="hl" style="color:{m.group(1)}">{m.group(2)}</span>',
        text,
    )
    # Strip residual newlines
    text = text.replace("\r", "").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # Final defence: still bare pipe / empty after normalization → None
    if not text or text == "|":
        return None
    # Highlight bare numbers inside (parentheses), e.g. "Duration: (180)s".
    # These never appear inside the wrapping <span class="hl">…</span> from the
    # game's color tags, so substitution is safe.
    text = PAREN_NUMBER_RE.sub(
        lambda m: f"({HL_OPEN}{m.group(1)}{HL_CLOSE})",
        text,
    )
    return text


def split_tiers(text):
    """Split a buff_description / alt_effect on ' | ' into tier1/tier2."""
    if text is None:
        return (None, None)
    raw = text.strip()
    if not raw or raw == "|":
        return (None, None)
    parts = raw.split(" | ")
    if len(parts) == 1:
        norm = normalize_html(parts[0])
        return (norm, norm)
    tier1 = normalize_html(parts[0])
    tier2 = normalize_html(parts[1])
    return (tier1, tier2)


def compute_best_recipes(dishes_list):
    """For each dish, pick the recipe most preferable for first-cook unlock.

    Cooking is a deterministic exact-multiset lookup of size N → dish: a
    2-ingredient pick (Fish, Tomato) and a 3-ingredient pick (Fish, Tomato, X)
    are two different lookups, so a 2-ingredient recipe never "collides" with a
    3-ingredient one at runtime. Score uses EXACT multiset equality (not
    sub-multiset). Since the CSV maps each multiset to exactly one dish, every
    score should come out to 0 — we still compute it as a sanity check.
    Tiebreaker: fewer TOTAL ingredients (prefer the 2-ingredient pair recipe),
    then first index.
    """
    dish_recipe_counters = [
        [Counter(r) for r in d["recipes"]] for d in dishes_list
    ]

    for di, dish in enumerate(dishes_list):
        my_recipes = dish_recipe_counters[di]
        best_idx = 0
        best_score = None
        best_total = None
        for ri, req in enumerate(my_recipes):
            score = 0
            for dj, other_recipes in enumerate(dish_recipe_counters):
                if dj == di:
                    continue
                if any(other == req for other in other_recipes):
                    score += 1
            total = sum(req.values())
            if (best_score is None
                    or score < best_score
                    or (score == best_score and total < best_total)):
                best_score = score
                best_total = total
                best_idx = ri
        dish["best_recipe_index"] = best_idx
        dish["best_recipe_score"] = best_score


ALT_GROUPS_DEF = [
    ("alt_random",      "Random Buff",         lambda s: "Life is like a platter" in s),
    ("alt_doll_perm",   "Permanent Doll Buff", lambda s: "Long-term consumption" in s or "increases Affinity" in s),
    ("alt_phase_clash", "Only in Phase Clash", lambda s: "Phase Clash" in s),
    ("alt_ashen_tales", "Only in Ashen Tales", lambda s: "Ashen Tales" in s),
]

ALT_GROUPS_RU = {
    "alt_random":      "Случайный бафф",
    "alt_doll_perm":   "Перманентный бафф",
    "alt_phase_clash": "Только в Phase Clash",
    "alt_ashen_tales": "Только в Ashen Tales",
}


def classify_alt(alt_raw):
    """Classify alt_effect raw text into a semantic group id, or None if empty."""
    if not alt_raw or not alt_raw.strip():
        return None
    for gid, _label, pred in ALT_GROUPS_DEF:
        if pred(alt_raw):
            return gid
    return None


def build_dish_sprite_map(rows):
    """Map dish_name -> (sprite_index, sprite_file) using LobbyCookIllustrationsData.json.

    Strategy:
      1. Take CSV rows with id in [PAIR_ID_FIRST, PAIR_ID_LAST] — the 55 canonical
         2-ingredient pair recipes, one per unique dish.
      2. Take all 55 entries from the illustrations JSON, sorted by field_1.
      3. The two sequences are in 1:1 order. Verify this by:
           a. building ingredient_id -> name from self-pair entries (X,X) ↔ "Y | Y";
           b. asserting every non-self-pair entry's parsed ingredient multiset
              matches the CSV row's ingredient multiset.
      4. Each illustration's field_10 is the sprite for the corresponding row's dish.
    """
    with open(ILLUSTRATIONS_PATH, encoding="utf-8") as f:
        illustrations = json.load(f)["data"]
    illustrations.sort(key=lambda e: e["field_1"])

    pair_rows = sorted(
        (r for r in rows if PAIR_ID_FIRST <= int(r["id"]) <= PAIR_ID_LAST),
        key=lambda r: int(r["id"]),
    )

    assert len(illustrations) == 55, f"expected 55 illustrations, got {len(illustrations)}"
    assert len(pair_rows) == 55, f"expected 55 pair rows, got {len(pair_rows)}"

    def parse_pair(field_7):
        a, b = field_7.split(",")
        return int(a.strip()), int(b.strip())

    def row_ingredients(row):
        return [s.strip() for s in row["ingredients"].split("|")]

    # Build ingredient_id -> name from self-pair rows.
    ing_id_to_name = {}
    for ill, row in zip(illustrations, pair_rows):
        a, b = parse_pair(ill["field_7"])
        if a == b:
            ings = row_ingredients(row)
            assert len(ings) == 2 and ings[0] == ings[1], (
                f"illustration {ill['field_1']} self-pair ({a},{a}) "
                f"does not match CSV row {row['id']} ingredients {ings}"
            )
            existing = ing_id_to_name.get(a)
            assert existing is None or existing == ings[0], (
                f"ingredient id {a} already mapped to '{existing}', "
                f"new mapping '{ings[0]}'"
            )
            ing_id_to_name[a] = ings[0]
    assert len(ing_id_to_name) == 10, (
        f"expected 10 ingredient ids, got {len(ing_id_to_name)}: {ing_id_to_name}"
    )
    print(f"[build] ingredient id map: {sorted(ing_id_to_name.items())}")

    # Verify every illustration entry pair matches its CSV row's ingredient multiset.
    dish_sprite_map = {}
    for ill, row in zip(illustrations, pair_rows):
        a, b = parse_pair(ill["field_7"])
        parsed = sorted([ing_id_to_name[a], ing_id_to_name[b]])
        actual = sorted(row_ingredients(row))
        assert parsed == actual, (
            f"illustration {ill['field_1']} ingredients {parsed} "
            f"do not match CSV row {row['id']} ingredients {actual}"
        )
        sprite_name = ill["field_10"]
        sprite_file = f"{sprite_name}.png"
        sprite_index = int(sprite_name.rsplit("_", 1)[1])
        dish_name = row["results"].strip()
        assert dish_name not in dish_sprite_map, (
            f"dish '{dish_name}' has duplicate sprite assignment"
        )
        dish_sprite_map[dish_name] = (sprite_index, sprite_file)

    return dish_sprite_map


def main():
    csv_path = find_csv()
    print(f"[build] reading {csv_path}")

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"[build] recipes: {len(rows)}")

    dish_sprite_map = build_dish_sprite_map(rows)
    print(f"[build] dish->sprite map built: {len(dish_sprite_map)} entries")

    dishes = OrderedDict()  # name -> dish dict

    used_alt_groups = set()
    unclassified = []

    for row in rows:
        rid = int(row["id"])
        name = row["results"].strip()
        ingredients = [s.strip() for s in row["ingredients"].split("|")]
        food_type = row["food_type_label"].strip()
        buff_raw = row["buff_description"]
        alt_raw = row["alt_effect"]

        sprite_index, sprite_file = dish_sprite_map[name]
        sprite_idx = sprite_index

        buff_t1, buff_t2 = split_tiers(buff_raw)
        alt_t1, alt_t2 = split_tiers(alt_raw)

        # Alt group: semantic classification
        agid = classify_alt(alt_raw)
        if agid is None and alt_raw and alt_raw.strip():
            unclassified.append((name, alt_raw.strip()[:80]))

        # Permanent Doll Buff dishes have no main buff_description in CSV;
        # promote the alt-effect text into buff_tier1/2 and drop the alt fields,
        # so the description shows as the dish's primary buff.
        if agid == "alt_doll_perm":
            buff_t1 = buff_t1 or alt_t1
            buff_t2 = buff_t2 or alt_t2
            alt_t1 = None
            alt_t2 = None
            agid = None

        if agid:
            used_alt_groups.add(agid)

        if name not in dishes:
            dishes[name] = {
                "id": len(dishes) + 1,
                "name": name,
                "sprite": sprite_file,
                "sprite_index": sprite_idx,
                "food_type": food_type,
                "buff_tier1": buff_t1,
                "buff_tier2": buff_t2,
                "alt_tier1": alt_t1,
                "alt_tier2": alt_t2,
                "alt_group": agid,
                "recipes": [],
                "recipe_ids": [],
                "ingredients_set": set(),
            }
        d = dishes[name]
        d["recipes"].append(ingredients)
        d["recipe_ids"].append(rid)
        for ing in ingredients:
            d["ingredients_set"].add(ing)

    # Convert sets to sorted lists
    dishes_list = []
    for d in dishes.values():
        d["ingredients"] = sorted(d.pop("ingredients_set"))
        dishes_list.append(d)

    # Collect dictionaries
    food_types = sorted({d["food_type"] for d in dishes_list})
    used_ingredients = {i for d in dishes_list for i in d["ingredients"]}
    # Include all known ingredients (even ones with no recipes yet),
    # so the sidebar can list them as soon as the icons exist.
    all_ingredients = sorted(used_ingredients | set(INGREDIENT_FILES.keys()))
    ingredient_icons = {
        name: ingredient_icon_filename(name) for name in all_ingredients
    }
    # Warn about ingredients used in CSV but missing a sprite mapping.
    missing_icons = sorted(used_ingredients - set(INGREDIENT_FILES.keys()))
    for name in missing_icons:
        print(f"[warn] no ingredient sprite mapping for '{name}'")

    alt_groups_out = [
        {"id": gid, "label": label, "label_ru": ALT_GROUPS_RU.get(gid, label)}
        for gid, label, _pred in ALT_GROUPS_DEF
        if gid in used_alt_groups
    ]

    # Best-recipe computation (uniqueness score across all dishes).
    compute_best_recipes(dishes_list)

    dish_unlock_bonuses = [
        {"ingredient": ing, "text": normalize_html(raw)}
        for ing, raw in DISH_UNLOCK_BONUSES
    ]

    out = {
        "dishes": dishes_list,
        "food_types": food_types,
        "ingredients": all_ingredients,
        "ingredient_icons": ingredient_icons,
        "alt_groups": alt_groups_out,
        "dish_unlock_bonuses": dish_unlock_bonuses,
        "stats": {
            "total_recipes": len(rows),
            "unique_dishes": len(dishes_list),
            "alt_groups": len(alt_groups_out),
        },
    }

    os.makedirs(os.path.dirname(DATA_DST), exist_ok=True)
    with open(DATA_DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[build] wrote {DATA_DST}")
    print(f"[build] unique dishes: {len(dishes_list)}")
    print(f"[build] alt groups: {len(alt_groups_out)}")
    for gid, _label, _pred in ALT_GROUPS_DEF:
        if gid not in used_alt_groups:
            print(f"[warn] alt group '{gid}' is defined but unused")
    for name, snippet in unclassified:
        print(f"[warn] unclassified alt-effect for dish '{name}': {snippet}")

    # Copy sprites
    os.makedirs(SPRITES_DST, exist_ok=True)
    copied = 0
    for d in dishes_list:
        src = os.path.join(SPRITES_SRC, d["sprite"])
        dst = os.path.join(SPRITES_DST, d["sprite"])
        if os.path.exists(src):
            shutil.copy2(src, dst)
            copied += 1
        else:
            print(f"[warn] missing sprite: {src}")
    print(f"[build] copied {copied} sprites to {SPRITES_DST}")

    # Copy ingredient icons (renamed to URL-safe filenames)
    os.makedirs(INGREDIENTS_DST, exist_ok=True)
    ing_copied = 0
    for name, src_filename in INGREDIENT_FILES.items():
        src = os.path.join(INGREDIENTS_SRC, src_filename)
        dst = os.path.join(INGREDIENTS_DST, ingredient_icon_filename(name))
        if os.path.exists(src):
            shutil.copy2(src, dst)
            ing_copied += 1
        else:
            print(f"[warn] missing ingredient sprite: {src}")
    print(f"[build] copied {ing_copied} ingredient icons to {INGREDIENTS_DST}")

    # Sanity checks
    assert len(dishes_list) == 55, f"expected 55 unique dishes, got {len(dishes_list)}"
    assert sum(len(d["recipe_ids"]) for d in dishes_list) == len(rows)
    assert not unclassified, f"unclassified alt-effects: {unclassified}"
    # No bare pipes / unsubstituted placeholders left in any buff/alt text.
    for d in dishes_list:
        for fld in ("buff_tier1", "buff_tier2", "alt_tier1", "alt_tier2"):
            v = d.get(fld)
            if v is None:
                continue
            assert v.strip() != "|", f"dish '{d['name']}' field {fld} is bare '|'"
            assert "{0}" not in v, f"dish '{d['name']}' field {fld} still has '{{0}}'"
        assert "best_recipe_index" in d, f"dish '{d['name']}' missing best_recipe_index"
        assert 0 <= d["best_recipe_index"] < len(d["recipes"])
    assert len(dish_unlock_bonuses) == 10, f"expected 10 dish-unlock bonuses, got {len(dish_unlock_bonuses)}"
    for entry in dish_unlock_bonuses:
        assert entry["ingredient"] in INGREDIENT_FILES, (
            f"dish-unlock bonus ingredient '{entry['ingredient']}' not in INGREDIENT_FILES"
        )

    # Best-recipe summary
    score_dist = Counter(d["best_recipe_score"] for d in dishes_list)
    guaranteed = score_dist.get(0, 0)
    print(f"[build] best_recipe: {guaranteed} guaranteed, "
          f"score distribution {dict(sorted(score_dist.items()))}")
    print("[build] OK")


if __name__ == "__main__":
    main()
