# portfolio

Source for **https://plotbot2023.github.io/portfolio** — a Quarto site that publishes Jupyter notebooks as readable web pages.

## Layout

```
_quarto.yml        site config (nav, theme, output dir, execution policy)
index.qmd          landing page
projects.qmd       listing page (auto-populated from notebooks/)
about.qmd          bio
resume.qmd         résumé + PDF download
styles.scss        light theme
styles-dark.scss   dark theme
styles.css         shared layout rules
notebooks/*.ipynb  the published work
assets/            résumé PDF, favicon
docs/              rendered site — this is what GitHub Pages serves
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

3. `quarto render`, then commit and push. The Projects listing picks it up automatically.

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
