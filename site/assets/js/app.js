/* GFL2 Dishes Library — vanilla JS app */
(function () {
  "use strict";

  const STATE = {
    lang: localStorage.getItem("gfl2_lang") || "en",
    data: null,
    filters: {
      food_type: new Set(),
      ingredient: new Map(), // ingredient name -> count (1 or 2)
      alt: new Set(),
    },
    search: "",
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ─── i18n helpers ────────────────────────────────────────────
  function tr(key) { return window.t(STATE.lang, key); }
  function trFoodType(ft) {
    const dict = window.I18N[STATE.lang].food_types || {};
    return dict[ft] || ft;
  }
  function trIngredient(ing) {
    const dict = window.I18N[STATE.lang].ingredients || {};
    return dict[ing] || ing;
  }

  function applyI18n() {
    document.documentElement.lang = STATE.lang;
    $$("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const v = tr(key);
      if (typeof v === "string") el.textContent = v;
    });
    $$("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      const v = tr(key);
      if (typeof v === "string") el.placeholder = v;
    });
  }

  // ─── Badge class ─────────────────────────────────────────────
  function badgeClass(food_type) {
    switch (food_type) {
      case "Dine In (General)": return "badge dine-general";
      case "Dine In (Random Effect)": return "badge dine-random";
      case "Take Out (Game Mode Buff)": return "badge takeout";
      case "Buff Doll (Perm Stat Boost)": return "badge doll-perm";
      case "Buff Doll (Other)": return "badge doll-other";
      default: return "badge";
    }
  }

  // ─── Filter chip rendering ───────────────────────────────────
  function ingredientIconUrl(name) {
    const file = STATE.data && STATE.data.ingredient_icons && STATE.data.ingredient_icons[name];
    return file ? `assets/ingredients/${encodeURIComponent(file)}` : null;
  }

  // Total count budget across all ingredient chips (matches a recipe of size 3).
  const INGREDIENT_BUDGET = 3;
  const INGREDIENT_PER_CHIP_MAX = 2;

  function ingredientTotal() {
    let n = 0;
    STATE.filters.ingredient.forEach((v) => { n += v; });
    return n;
  }

  function renderChips(container, items, store, labelFn, options = {}) {
    container.innerHTML = "";
    const isCounter = options.counter === true;
    items.forEach((value) => {
      const chip = document.createElement("button");
      chip.type = "button";
      let cls = "chip";
      if (options.altClass) cls += " alt-chip";
      if (options.iconFn) cls += " ingredient-chip";
      chip.className = cls;
      const label = labelFn(value);
      const iconHtml = options.iconFn
        ? (() => {
            const icon = options.iconFn(value);
            return icon ? `<img class="chip-icon" src="${icon}" alt="" loading="lazy" />` : "";
          })()
        : "";

      const renderInner = () => {
        const count = isCounter ? (store.get(value) || 0) : 0;
        const badgeHtml = (isCounter && count > 0)
          ? `<span class="chip-count">×${count}</span>`
          : "";
        if (options.iconFn) {
          chip.innerHTML = `${iconHtml}<span>${escapeHtml(label)}</span>${badgeHtml}`;
        } else if (options.altClass) {
          chip.innerHTML = `<span title="${escapeAttr(label)}">${escapeHtml(label)}</span>`;
        } else {
          chip.textContent = label;
        }
        chip.classList.toggle("active",
          isCounter ? count > 0 : store.has(value));
        chip.classList.toggle("count-2", isCounter && count >= 2);
      };
      renderInner();

      chip.addEventListener("click", () => {
        if (isCounter) {
          const cur = store.get(value) || 0;
          let next = cur + 1;
          if (next > INGREDIENT_PER_CHIP_MAX) next = 0;
          // Enforce total budget; if adding would exceed, snap to 0.
          if (next > cur && (ingredientTotal() - cur + next) > INGREDIENT_BUDGET) {
            next = 0;
          }
          if (next === 0) store.delete(value);
          else store.set(value, next);
        } else {
          if (store.has(value)) store.delete(value);
          else store.add(value);
        }
        renderInner();
        render();
      });
      container.appendChild(chip);
    });
  }

  function buildFilters() {
    const d = STATE.data;
    renderChips(
      $("#filter-food-type"),
      d.food_types,
      STATE.filters.food_type,
      trFoodType
    );
    renderChips(
      $("#filter-ingredient"),
      d.ingredients,
      STATE.filters.ingredient,
      trIngredient,
      { iconFn: ingredientIconUrl, counter: true }
    );
    renderChips(
      $("#filter-alt"),
      d.alt_groups.map((g) => g.id),
      STATE.filters.alt,
      (id) => {
        const dict = window.I18N[STATE.lang].alt_groups || {};
        return dict[id] || id;
      },
      { altClass: true }
    );
  }

  // ─── Filtering logic ─────────────────────────────────────────
  function dishMatches(dish) {
    const f = STATE.filters;
    if (f.food_type.size && !f.food_type.has(dish.food_type)) return false;
    if (f.ingredient.size) {
      // Multiset filter: dish matches if at least one recipe has ≥ count of each
      // selected ingredient (sub-multiset of the recipe).
      const required = [];
      f.ingredient.forEach((n, ing) => { if (n > 0) required.push([ing, n]); });
      if (required.length) {
        const ok = dish.recipes.some((recipe) => {
          const counts = {};
          for (const ing of recipe) counts[ing] = (counts[ing] || 0) + 1;
          return required.every(([ing, n]) => (counts[ing] || 0) >= n);
        });
        if (!ok) return false;
      }
    }
    if (f.alt.size && !f.alt.has(dish.alt_group)) return false;

    if (STATE.search) {
      const q = STATE.search.toLowerCase();
      const hay = [
        dish.name,
        dish.buff_tier1 || "",
        dish.buff_tier2 || "",
        dish.alt_tier1 || "",
        dish.alt_tier2 || "",
        dish.ingredients.join(" "),
        dish.food_type,
      ].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  // ─── Card rendering ──────────────────────────────────────────
  function renderCard(dish) {
    const card = document.createElement("article");
    card.className = "card";
    card.tabIndex = 0;

    const buffPreview = dish.buff_tier2 || dish.buff_tier1 || "";
    const altLine = dish.alt_tier2 || dish.alt_tier1 || null;

    card.innerHTML = `
      <div class="card-head">
        <img class="card-sprite" src="assets/sprites/${dish.sprite}" alt="${escapeAttr(dish.name)}" loading="lazy" />
        <div class="card-title-block">
          <h3 class="card-title">${escapeHtml(dish.name)}</h3>
          <span class="${badgeClass(dish.food_type)}">${escapeHtml(trFoodType(dish.food_type))}</span>
        </div>
      </div>
      <div class="tier-text">${buffPreview || "&nbsp;"}</div>
      ${altLine ? `<div class="alt-line">${altLine}</div>` : ""}
      <div class="recipes-toggle">${escapeHtml(tr("show_recipes"))} (${dish.recipe_ids.length})</div>
    `;

    card.addEventListener("click", () => openModal(dish));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openModal(dish);
      }
    });
    return card;
  }

  function render() {
    const grid = $("#grid");
    const empty = $("#empty");
    grid.innerHTML = "";
    let count = 0;
    STATE.data.dishes.forEach((dish) => {
      if (!dishMatches(dish)) return;
      grid.appendChild(renderCard(dish));
      count++;
    });
    $("#result-count").textContent = window.I18N[STATE.lang].result_count(count);
    empty.classList.toggle("hidden", count > 0);
  }

  // ─── Modal ───────────────────────────────────────────────────
  function openModal(dish) {
    const body = $("#modal-body");
    const bestIdx = (typeof dish.best_recipe_index === "number") ? dish.best_recipe_index : -1;
    const bestScore = dish.best_recipe_score;
    // Render recipes with the best one first.
    const orderedRecipes = dish.recipes.map((ings, i) => ({ ings, i }));
    if (bestIdx >= 0 && bestIdx < orderedRecipes.length) {
      const [best] = orderedRecipes.splice(bestIdx, 1);
      orderedRecipes.unshift(best);
    }
    const recipesHtml = orderedRecipes.map(({ ings, i }) => {
      const isBest = i === bestIdx;
      const badgeKey = (bestScore === 0) ? "recipe_badge_guaranteed" : "recipe_badge_recommended";
      const badgeCls = (bestScore === 0) ? "recipe-badge guaranteed" : "recipe-badge recommended";
      const badgeHtml = isBest
        ? `<span class="${badgeCls}" title="${escapeAttr(tr("best_recipe_hint"))}">${escapeHtml(tr(badgeKey))}</span>`
        : "";
      return `
      <li class="recipe-row${isBest ? " best" : ""}">
        <span class="recipe-id">#${dish.recipe_ids[i]}</span>
        ${ings.map((ing) => {
          const icon = ingredientIconUrl(ing);
          const iconHtml = icon ? `<img class="pill-icon" src="${icon}" alt="" loading="lazy" />` : "";
          return `<span class="ingredient-pill">${iconHtml}${escapeHtml(trIngredient(ing))}</span>`;
        }).join("")}
        ${badgeHtml}
      </li>
    `;
    }).join("");

    const extraBuffsHtml = (dish.food_type === "Dine In (General)"
                            && STATE.data.dish_unlock_bonuses)
      ? `
        <div class="modal-section extra-buffs-section">
          <h4>${escapeHtml(tr("dish_unlock_bonus_title"))}</h4>
          <p class="extra-buffs-hint">${escapeHtml(tr("dish_unlock_bonus_hint"))}</p>
          <ul class="extra-buffs-list">
            ${STATE.data.dish_unlock_bonuses.map((eb) => {
              const icon = ingredientIconUrl(eb.ingredient);
              const iconHtml = icon ? `<img class="pill-icon" src="${icon}" alt="" loading="lazy" />` : "";
              return `
              <li class="extra-buff-row">
                <span class="ingredient-pill">${iconHtml}${escapeHtml(trIngredient(eb.ingredient))}</span>
                <div class="extra-buff-text">${eb.text}</div>
              </li>`;
            }).join("")}
          </ul>
        </div>
      `
      : "";

    const altSection = (dish.alt_tier1 || dish.alt_tier2) ? `
      <div class="modal-section">
        <h4>${escapeHtml(tr("alt_effect"))}</h4>
        ${dish.alt_tier1 ? `<div class="tier-block"><span class="tier-label">${tr("tier1")}</span><div>${dish.alt_tier1}</div></div>` : ""}
        ${dish.alt_tier2 && dish.alt_tier2 !== dish.alt_tier1 ? `<div class="tier-block"><span class="tier-label">${tr("tier2")}</span><div>${dish.alt_tier2}</div></div>` : ""}
      </div>
    ` : "";

    body.innerHTML = `
      <div class="modal-head">
        <img class="modal-sprite" src="assets/sprites/${dish.sprite}" alt="${escapeAttr(dish.name)}" />
        <div>
          <h2 class="modal-title">${escapeHtml(dish.name)}</h2>
          <span class="${badgeClass(dish.food_type)}">${escapeHtml(trFoodType(dish.food_type))}</span>
        </div>
      </div>

      <div class="modal-section">
        <h4>${escapeHtml(tr("buff"))}</h4>
        ${dish.buff_tier1 ? `<div class="tier-block"><span class="tier-label">${tr("tier1")}</span><div>${dish.buff_tier1}</div></div>` : ""}
        ${dish.buff_tier2 && dish.buff_tier2 !== dish.buff_tier1 ? `<div class="tier-block"><span class="tier-label">${tr("tier2")}</span><div>${dish.buff_tier2}</div></div>` : ""}
      </div>

      ${altSection}

      <div class="modal-section">
        <h4>${escapeHtml(tr("recipes"))} (${dish.recipe_ids.length})</h4>
        <ul class="recipe-list">${recipesHtml}</ul>
      </div>

      ${extraBuffsHtml}
    `;
    $("#modal").classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    $("#modal").classList.add("hidden");
    document.body.style.overflow = "";
  }

  // ─── Helpers ─────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }
  function escapeAttr(s) { return escapeHtml(s); }

  // ─── Bootstrap ───────────────────────────────────────────────
  function setLang(lang) {
    STATE.lang = lang;
    localStorage.setItem("gfl2_lang", lang);
    $$(".lang-btn").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
    applyI18n();
    buildFilters();
    render();
  }

  function init(data) {
    STATE.data = data;
    applyI18n();
    buildFilters();
    render();

    // Search
    $("#search").addEventListener("input", (e) => {
      STATE.search = e.target.value.trim();
      render();
    });

    // Lang switch
    $$(".lang-btn").forEach((b) => {
      b.addEventListener("click", () => setLang(b.dataset.lang));
      if (b.dataset.lang === STATE.lang) b.classList.add("active");
      else b.classList.remove("active");
    });

    // Reset filters
    $("#reset-filters").addEventListener("click", () => {
      STATE.filters.food_type.clear();
      STATE.filters.ingredient.clear(); // Map.clear()
      STATE.filters.alt.clear();
      STATE.search = "";
      $("#search").value = "";
      buildFilters();
      render();
    });

    // Modal close
    $$("[data-close]").forEach((el) => el.addEventListener("click", closeModal));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
  }

  fetch("data/dishes.json")
    .then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(init)
    .catch((err) => {
      console.error(err);
      $("#grid").innerHTML =
        `<div class="empty">Failed to load data.<br>If you opened the file directly, please serve it via <code>python -m http.server</code>.</div>`;
    });
})();
