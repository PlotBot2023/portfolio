# portfolio

Source for **https://plotbot2023.github.io/portfolio** — a Quarto site that publishes Jupyter notebooks as readable web pages.

## Layout

```
_quarto.yml          site config (nav, theme, output dir, execution policy)
index.qmd            home         projects.qmd         projects      | each one screen at 1920x1080, 1536x864 and 1366x768
about.qmd            about         | (no scrolling on a desktop); they stack and scroll on a phone
resume.qmd           résumé       /
_notebooks.ejs       the Notebooks tab on Projects, drawn from notebooks/ automatically
styles.scss          theme: the Hub's field-matchup navy palette and finishes, plus the 16 px floor
styles.css           the single-view layout and components (panels, tiles, stage, chips, notes)
assets/sv.js         tabs, tile picking and #links on Projects and Résumé
assets/notebooks/    one chart per notebook for the Projects tiles (tools/notebook_thumbs.py)
tools/               notebook_thumbs.py, measure_pages.py (the standards check, below)
notebooks/*.ipynb    the published work
docs/                rendered site, what GitHub Pages serves (keep docs/.nojekyll)
```

## Standards

The four main pages follow the owner's standards (SportsAnalytics `docs/RULES_OF_CLAUDE.md` rules 29 to 34): no text
under 16 px, contrast at least 7:1 for body text and 4.5:1 for secondary text, every target at least 44 px, status
as a shape plus a word, no symbols a screen reader announces (`&`, middle dots, dashes, arrows, slashes, emoji) in
visible text or accessible names, real alt text, no motion, and each page one view. Longer text sits one click away
in a note (a native `popover`). Check a change in a browser before publishing:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory docs
python tools/measure_pages.py
```

## First-time setup

From inside this folder:

```bash
git init
git add -A
git commit -m "Portfolio site"
git branch -M main
git remote add origin https://github.com/PlotBot2023/portfolio.git
git push -u origin main
```

Then on GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main`, folder: `/docs`** → Save.

The site goes live at **https://plotbot2023.github.io/portfolio** in a minute or two.

## Publishing a change

```bash
quarto render          # writes to docs/
git add -A
git commit -m "update"
git push
```

GitHub Pages serves `docs/` on the `main` branch. The site is live a minute or so after the push.

## Adding a notebook

1. Copy the `.ipynb` into `notebooks/`.
2. Add a **raw cell as the very first cell** with YAML front matter:

   ```yaml
   ---
   title: "Your Title"
   description: "One or two sentences. This is what shows on the Projects page."
   date: "2026-08-21"
   categories:
     - Python
     - PostgreSQL
   order: 10
   toc: true
   ---
   ```

3. Add a line for it in `tools/notebook_thumbs.py` (which saved chart to use) and its alt text in `_notebooks.ejs`,
   run `python tools/notebook_thumbs.py`, then `quarto render`. The Notebooks tab picks it up automatically.
   `quarto render` deletes `docs/.nojekyll`; put it back before committing.

`order` controls position on the Projects page (lower = higher up).

## Notebook execution

`_quarto.yml` sets `execute: enabled: false`. Notebooks are published **with their saved outputs** and are not re-run at render time — several read from a local PostgreSQL instance and local CSV exports that no other machine can reach.

This means: **whatever is saved in the `.ipynb` is what gets published.** Run the notebook in Jupyter, save it with outputs, then render.

To re-execute on a machine that does have the data, set `enabled: true` in `_quarto.yml` (or add `execute: enabled: true` to a single notebook's front matter).

## Before you commit

Notebooks can carry secrets in code *and* in saved output. Run a quick check:

```bash
grep -rEn "postgres(ql)?://|password\s*=\s*['\"]|api[_-]?key\s*=\s*['\"]|C:\\\\Users" notebooks/ || echo "clean"
```

Connection details belong in environment variables (`os.environ.get("PS_DB_PASS")`), never inline.

## Local setup

```bash
# Quarto CLI: https://quarto.org/docs/get-started/
quarto preview        # live-reloading local server
quarto render         # one-off build into docs/
```

No Python environment is needed to render, since notebooks aren't executed.
