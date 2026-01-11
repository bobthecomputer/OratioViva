# Repository Guidelines

## Project Structure & Module Organization
- This repo may contain multiple small projects. Place each project under its own folder (for example, `project-name/`) with a local `README.md`.
- Prefer `src/` for application code (e.g., `project-name/src/`) and `tests/` for tests mirroring the package layout (e.g., `tests/test_module.py`).
- Put helper scripts in `scripts/` and non-code assets in `assets/`.
- Use a single `pyproject.toml` or per-project `requirements.txt`. If a folder uses Node, keep its `package.json` inside that folder.

## Build, Test, and Development Commands
- Python venv (Unix/macOS): `python -m venv .venv && source .venv/bin/activate`
- Python venv (Windows): `.venv\\Scripts\\activate`
- Install deps: `pip install -r requirements.txt` or `pip install -e .` (if `pyproject.toml`/`setup.cfg` present)
- Run tests: `pytest -q`
- Lint/format (if configured): `ruff check .` and `black .`
- Node subproject (if `package.json` exists): `npm ci && npm test`

## Coding Style & Naming Conventions
- Python: 4-space indent, 88-char line length, `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Prefer type hints and docstrings. Run `mypy .` when a config exists.
- Keep modules focused; avoid large, multi-purpose files. Group related code by feature within `src/`.

## Testing Guidelines
- Framework: `pytest`. Name tests `test_*.py` and colocate fixtures under `tests/fixtures/`.
- Aim for ≥80% coverage. Example: `pytest --cov=src --cov-report=term-missing`.
- Write tests for bug fixes first; reproduce with a failing test, then fix.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`. Example: `fix: handle empty input in parser`.
- PRs: include a clear description, linked issues (`Closes #123`), and screenshots/logs when helpful. Keep PRs focused and under ~300 lines when possible.

## Agent-Specific Instructions
- Follow this file’s conventions for any folder you touch. Prefer minimal, targeted patches and do not modify unrelated files.
- Before finishing, run available linters/tests in the touched project. Use `rg` to navigate quickly and read files in small chunks.
