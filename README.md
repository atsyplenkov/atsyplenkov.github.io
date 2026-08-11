# My Personal website
[![Based on Tufted Blog Template](https://img.shields.io/badge/based%20on-Tufted%20Blog%20Template-239DAD?logo=github)](https://github.com/Yousa-Mirage/Tufted-Blog-Template)

Built with [Typst](https://typst.app/) from the [Tufted Blog Template](https://github.com/Yousa-Mirage/Tufted-Blog-Template).

Published content is [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Template code remains under the MIT license.

## Requirements

- [Typst](https://typst.app/docs/reference/cli/) CLI
- [uv](https://docs.astral.sh/uv/) (for the Python build/audit scripts)

## Build

```bash
uv run build.py build          # write _site/
uv run build.py build --force  # rebuild everything
```

## Preview

```bash
uv run build.py preview        # http://localhost:8000 (livereload)
uv run build.py preview -p 3000
```

## Check

Clean production build + black-box audit (what CI runs):

```bash
uv run scripts/accept.py
```

Audit an existing tree only:

```bash
uv run scripts/audit_site.py --site _site
```
