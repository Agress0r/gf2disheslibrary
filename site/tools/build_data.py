"""
Build site/data/dishes.json from LobbyCookWildcardLookup.json
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
LOOKUP_JSON_CANDIDATES = [
    os.path.join(ROOT, "LobbyCookWildcardLookup.json"),
]
ILLUSTRATIONS_CANDIDATES = [
    os.path.join(ROOT, "LobbyCookIllustrationsData.decoded.json"),
    os.path.join(ROOT, "LobbyCookIllustrationsData.json"),
]
SPRITES_SRC = os.path.join(ROOT, "DishesImages", "Sprite")
SPRITES_DST = os.path.join(SITE, "assets", "sprites")
INGREDIENTS_SRC = os.path.join(ROOT, "Ingredients", "Sprite")
INGREDIENTS_DST = os.path.join(SITE, "assets", "ingredients")
DATA_DST = os.path.join(SITE, "data", "dishes.json")

# All 2-ingredient recipes are the canonical "wildcard pair" recipes:
# one per unique dish. They line up 1:1, in order, with entries in
# LobbyCookIllustrationsData*.json, which is the authoritative source for
# sprite assignment via field_10.
PAIR_RECIPE_SIZE = 2

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
    "Onion": "Onion.png",
    "Purple Sweet Potato": "Purple Sweet Potato.png",
    "Synthetic Fish": "Synthetic Fish.png",
    "Synthetic Meat": "Synthetic Meat.png",
    "Synthetic Poultry": "Synthetic Poultry.png",
    "Tofu": "Tofu.png",
    "Tomato": "Tomato.png",
    "Wheat": "Wheat.png",
    "White Rice": "White Rice.png",
    "Synthetic Fish Meat": "Synthetic Fish.png",
    "Synthetic Red Meat": "Synthetic Meat.png",
    "Synthetic White Meat": "Synthetic Poultry.png",
    "Rice": "White Rice.png",
    "Grains": "Wheat.png",
}


def ingredient_icon_filename(name):
    """Normalized, URL-safe filename for an ingredient sprite."""
    return name.replace(" ", "_") + ".png"

COLOR_RE = re.compile(r"<color=(#[0-9a-fA-F]{6})>(.*?)</color>", re.DOTALL)

ACCENT = "#f26c1c"
HL_OPEN = f'<span class="hl" style="color:{ACCENT}">'
HL_CLOSE = "</span>"

PLACEHOLDER_VALUES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "placeholder_values.json"
)

# Sentinel for unknown {0} values (null in placeholder_values.json).
PLACEHOLDER_UNKNOWN = "?"

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


def find_lookup_json():
    for p in LOOKUP_JSON_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def find_illustrations_json():
    for p in ILLUSTRATIONS_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit(f"Illustrations JSON not found in: {ILLUSTRATIONS_CANDIDATES}")


def load_rows():
    json_path = find_lookup_json()
    if json_path:
        print(f"[build] reading {json_path}")
        with open(json_path, encoding="utf-8-sig") as f:
            return json.load(f)["data"]

    csv_path = find_csv()
    print(f"[build] reading {csv_path}")
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def normalize_html(text, placeholder_values=None, dish_name=None):
    """Convert Unity <color=#xxx>...</color> tags to <span class='hl'>.

    Also: returns None for empty/whitespace/bare-pipe input, highlights
    {0} placeholders (per-dish value from placeholder_values.json) and
    numbers inside (parentheses).
    """
    if text is None:
        return None
    text = text.strip()
    if not text or text == "|":
        return None
    # Substitute {0} placeholder with per-dish value BEFORE color-tag conversion,
    # so a wrapping <color>...{0}...</color> ends up as a single span (not nested).
    if "{0}" in text:
        assert dish_name is not None, (
            f"text contains '{{0}}' but no dish_name provided for lookup"
        )
        assert placeholder_values is not None and dish_name in placeholder_values, (
            f"Dish '{dish_name}' has {{0}} placeholder but no entry in "
            f"placeholder_values.json — add it manually"
        )
        value = placeholder_values[dish_name]
        if value is None:
            value = PLACEHOLDER_UNKNOWN
        text = text.replace("{0}", value)
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


def split_tiers(text, placeholder_values=None, dish_name=None):
    """Split a buff_description / alt_effect on ' | ' into tier1/tier2."""
    if text is None:
        return (None, None)
    raw = text.strip()
    if not raw or raw == "|":
        return (None, None)
    parts = raw.split(" | ")
    kw = dict(placeholder_values=placeholder_values, dish_name=dish_name)
    if len(parts) == 1:
        norm = normalize_html(parts[0], **kw)
        return (norm, norm)
    tier1 = normalize_html(parts[0], **kw)
    tier2 = normalize_html(parts[1], **kw)
    return (tier1, tier2)


def compute_best_recipes(dishes_list):
    """For each dish, pick the recipe most preferable for first-cook unlock.

    Cooking is a deterministic exact-multiset lookup of size N -> dish: a
    2-ingredient pick (Fish, Tomato) and a 3-ingredient pick (Fish, Tomato, X)
    are two different lookups, so a 2-ingredient recipe never "collides" with a
    3-ingredient one at runtime. Score uses exact multiset equality (not
    sub-multiset). Since the lookup maps each multiset to exactly one dish, every
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
      1. Take all 2-ingredient pair recipes, one per unique dish.
      2. Take all entries from the illustrations JSON, sorted by field_1.
      3. The two sequences are in 1:1 order. Verify this by:
           a. building ingredient_id -> name from self-pair entries (X,X) -> "Y | Y";
           b. asserting every non-self-pair entry's parsed ingredient multiset
              matches the lookup row's ingredient multiset.
      4. Each illustration's field_10 is the sprite for the corresponding row's dish.
    """
    illustrations_path = find_illustrations_json()
    print(f"[build] reading {illustrations_path}")
    with open(illustrations_path, encoding="utf-8-sig") as f:
        illustrations = json.load(f)["data"]
    illustrations.sort(key=lambda e: e["field_1"])

    def parse_pair(field_7):
        a, b = field_7.split(",")
        return int(a.strip()), int(b.strip())

    def row_ingredients(row):
        return [s.strip() for s in row["ingredients"].split("|")]

    pair_rows = sorted(
        (r for r in rows if len(row_ingredients(r)) == PAIR_RECIPE_SIZE),
        key=lambda r: int(r["id"]),
    )

    unique_dish_count = len({r["results"].strip() for r in rows})
    assert len(illustrations) == unique_dish_count, (
        f"expected {unique_dish_count} illustrations, got {len(illustrations)}"
    )
    assert len(pair_rows) == unique_dish_count, (
        f"expected {unique_dish_count} pair rows, got {len(pair_rows)}"
    )

    # Build ingredient_id -> name from self-pair rows.
    ing_id_to_name = {}
    for ill, row in zip(illustrations, pair_rows):
        a, b = parse_pair(ill["field_7"])
        if a == b:
            ings = row_ingredients(row)
            assert len(ings) == 2 and ings[0] == ings[1], (
                f"illustration {ill['field_1']} self-pair ({a},{a}) "
                f"does not match lookup row {row['id']} ingredients {ings}"
            )
            existing = ing_id_to_name.get(a)
            assert existing is None or existing == ings[0], (
                f"ingredient id {a} already mapped to '{existing}', "
                f"new mapping '{ings[0]}'"
            )
            ing_id_to_name[a] = ings[0]
    # Newer data can add an ingredient that has no self-pair yet. Infer it from
    # a pair where the other side is already known.
    changed = True
    while changed:
        changed = False
        for ill, row in zip(illustrations, pair_rows):
            ids = list(parse_pair(ill["field_7"]))
            names = row_ingredients(row)
            if len(set(ids)) != 2 or len(set(names)) != 2:
                continue
            for known_idx, unknown_idx in ((0, 1), (1, 0)):
                known_id = ids[known_idx]
                unknown_id = ids[unknown_idx]
                known_name = ing_id_to_name.get(known_id)
                if known_name is None or unknown_id in ing_id_to_name:
                    continue
                if known_name not in names:
                    continue
                [unknown_name] = [name for name in names if name != known_name]
                ing_id_to_name[unknown_id] = unknown_name
                changed = True

    expected_ing_ids = {i for ill in illustrations for i in parse_pair(ill["field_7"])}
    missing_ing_ids = sorted(expected_ing_ids - set(ing_id_to_name))
    assert not missing_ing_ids, (
        f"unmapped illustration ingredient ids {missing_ing_ids}; "
        f"known map: {ing_id_to_name}"
    )
    print(f"[build] ingredient id map: {sorted(ing_id_to_name.items())}")

    # Verify every illustration entry pair matches its lookup row's ingredient multiset.
    dish_sprite_map = {}
    for ill, row in zip(illustrations, pair_rows):
        a, b = parse_pair(ill["field_7"])
        parsed = sorted([ing_id_to_name[a], ing_id_to_name[b]])
        actual = sorted(row_ingredients(row))
        assert parsed == actual, (
            f"illustration {ill['field_1']} ingredients {parsed} "
            f"do not match lookup row {row['id']} ingredients {actual}"
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
    rows = load_rows()
    print(f"[build] recipes: {len(rows)}")

    dish_sprite_map = build_dish_sprite_map(rows)
    print(f"[build] dish->sprite map built: {len(dish_sprite_map)} entries")

    # Per-dish {0} placeholder values (loaded from external JSON).
    with open(PLACEHOLDER_VALUES_PATH, encoding="utf-8") as f:
        placeholder_values = json.load(f)
    placeholder_values.pop("_comment", None)
    print(f"[build] placeholder values loaded: {len(placeholder_values)} entries")

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

        buff_t1, buff_t2 = split_tiers(buff_raw, placeholder_values, name)
        alt_t1, alt_t2 = split_tiers(alt_raw, placeholder_values, name)

        # Alt group: semantic classification
        agid = classify_alt(alt_raw)
        if agid is None and alt_raw and alt_raw.strip():
            unclassified.append((name, alt_raw.strip()[:80]))

        # Permanent Doll Buff dishes have no main buff_description in the lookup;
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
    # "ingredients" list = only recipe ingredients (used in sidebar filter).
    # Bonus-only ingredients (from INGREDIENT_FILES but not in any recipe)
    # are excluded from the filter — they only appear in dish_unlock_bonuses.
    all_ingredients = sorted(used_ingredients)
    # Icon map covers ALL known ingredients (recipe + bonus) so the
    # Extra First-Cook Bonuses section in the modal can render icons.
    all_icon_ingredients = sorted(used_ingredients | set(INGREDIENT_FILES.keys()))
    ingredient_icons = {
        name: ingredient_icon_filename(name)
        for name in all_icon_ingredients
        if name in INGREDIENT_FILES
    }
    # Warn about recipe ingredients missing a sprite mapping.
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
    unknown_placeholders = [n for n, v in placeholder_values.items() if v is None]
    for n in unknown_placeholders:
        print(f"[warn] dish '{n}' has unknown {{0}} value (null in placeholder_values.json)")

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
    assert len(dishes_list) == len(dish_sprite_map), (
        f"expected {len(dish_sprite_map)} unique dishes, got {len(dishes_list)}"
    )
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
