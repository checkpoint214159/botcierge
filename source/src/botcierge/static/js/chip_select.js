/* Chip picker for multi-selects (staff catalogue forms).

   Any <select multiple data-chips="placeholder"> becomes: the chosen options as chips with an ×,
   plus a search box that lists the options not chosen yet. The real <select> stays in the form
   (just hidden), and this script only ticks/unticks its options, so the server receives exactly
   what a plain multi-select would send. Without JavaScript the plain multi-select shows instead.

   Keys: type to filter, ↑/↓ to move, Enter to add, Backspace in an empty box removes the last chip,
   Esc closes the list. */
(function () {
  function enhance(select) {
    const box = document.createElement("div");
    box.className = "bc-chips";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = select.dataset.chips || "Add…";
    input.setAttribute("aria-label", input.placeholder);
    const menu = document.createElement("ul");
    menu.className = "bc-chips-menu";
    menu.hidden = true;
    let active = 0;

    select.hidden = true;
    select.after(box);
    // the field's <label for=...> should focus the search box now
    const label = document.querySelector(`label[for="${select.id}"]`);
    if (label) label.addEventListener("click", (e) => { e.preventDefault(); input.focus(); });

    function render() {
      box.replaceChildren();
      for (const opt of select.options) {
        if (!opt.selected) continue;
        const chip = document.createElement("span");
        chip.className = "bc-chip";
        chip.textContent = opt.text;
        const x = document.createElement("button");
        x.type = "button";
        x.innerHTML = "&times;";
        x.setAttribute("aria-label", `Remove ${opt.text}`);
        x.addEventListener("click", () => { opt.selected = false; render(); input.focus(); });
        chip.append(x);
        box.append(chip);
      }
      box.append(input, menu);
    }

    function matches() {
      const q = input.value.trim().toLowerCase();
      return [...select.options].filter((o) => !o.selected && o.text.toLowerCase().includes(q));
    }

    function openMenu() {
      const found = matches();
      menu.replaceChildren();
      active = Math.min(active, Math.max(found.length - 1, 0));
      found.forEach((opt, i) => {
        const li = document.createElement("li");
        li.textContent = opt.text;
        if (i === active) li.className = "active";
        // mousedown (not click) so it fires before the input loses focus and closes the menu
        li.addEventListener("mousedown", (e) => { e.preventDefault(); add(opt); });
        menu.append(li);
      });
      if (!found.length) {
        const li = document.createElement("li");
        li.className = "empty";
        li.textContent = input.value ? "No matches" : "Everything is already added";
        menu.append(li);
      }
      menu.hidden = false;
    }

    function add(opt) {
      opt.selected = true;
      input.value = "";
      active = 0;
      render();
      input.focus();
      openMenu();
    }

    input.addEventListener("focus", openMenu);
    input.addEventListener("input", () => { active = 0; openMenu(); });
    input.addEventListener("blur", () => { menu.hidden = true; });
    input.addEventListener("keydown", (e) => {
      const found = matches();
      if (e.key === "ArrowDown") { active = Math.min(active + 1, found.length - 1); openMenu(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); openMenu(); e.preventDefault(); }
      else if (e.key === "Enter") { e.preventDefault(); if (found[active]) add(found[active]); }  // never submit the form from here
      else if (e.key === "Escape") { menu.hidden = true; }
      else if (e.key === "Backspace" && !input.value) {
        const chosen = [...select.options].filter((o) => o.selected);
        if (chosen.length) { chosen[chosen.length - 1].selected = false; render(); input.focus(); }
      }
    });
    box.addEventListener("click", (e) => { if (e.target === box) input.focus(); });

    render();
  }

  document.querySelectorAll("select[multiple][data-chips]").forEach(enhance);
})();
