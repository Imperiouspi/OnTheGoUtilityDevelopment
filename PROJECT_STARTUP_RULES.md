# Project Startup Rules

Rules for Claude Code to follow when starting a new project in this repository.

## 1. Project Structure

Each project must live in its own individual top-level folder within the repository root. Do not nest projects inside other projects. The folder name should be a short, descriptive kebab-case name (e.g., `todo-cli`, `file-organizer`).

## 2. README Per Project

Each project folder must contain its own `README.md` with a brief description, usage instructions, and any dependencies required to run it.

## 3. .gitignore Hygiene

Each project should either use a shared root-level `.gitignore` or include its own. Build artifacts, `node_modules`, `__pycache__`, `.env` files, and other generated or sensitive files must never be committed.

## 4. Self-Contained Dependencies

Each project must be independently runnable. All dependency manifests (`package.json`, `requirements.txt`, `go.mod`, etc.) belong inside the project's own folder, not at the repo root.
