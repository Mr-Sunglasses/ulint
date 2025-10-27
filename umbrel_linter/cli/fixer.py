from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from rich.console import Console

from ..core.models import LintingError
from ..utils.filesystem import write_file_safely


def apply_fixes(root: Path, app_id: str | None, result, fix_secure: bool, console: Console) -> None:
    """Apply safe (and optionally secure) fixes to the project in-place.

    Args:
        root: Lint target path (app dir or app-store dir)
        app_id: Optional specific app to fix
        result: LintingResult containing errors
        fix_secure: Whether to apply secure fixes (e.g., add user: "1000:1000")
        console: Rich console for status output
    """
    # Group errors by file path to minimize IO
    by_file: dict[str, list[LintingError]] = {}
    for err in result.errors:
        by_file.setdefault(err.file, []).append(err)

    is_single_app_root = (root / "umbrel-app.yml").exists()

    for file_rel, errs in by_file.items():
        # Normalize file path relative to the provided root
        rel_path = file_rel
        # When linting a single app folder, reported files are prefixed with
        # the app_id (usually equal to root.name). Strip that prefix.
        if is_single_app_root:
            prefix = f"{(app_id or root.name)}/"
            if file_rel.startswith(prefix):
                rel_path = file_rel[len(prefix) :]

        file_path = (root / rel_path).resolve()
        if not str(file_path).startswith(str(root.resolve())):
            continue  # safety guard

        # Fix directory structure (empty_app_data_directory)
        for err in errs:
            if err.id == "empty_app_data_directory":
                dir_path = (root / err.file).resolve()
                gitkeep = dir_path / ".gitkeep"
                if write_file_safely(gitkeep, ""):
                    console.print(f"[green]Created[/green] {gitkeep}")

        # Fix missing APP_DATA_DIR mounted directories (skip files)
        for err in errs:
            if err.id == "missing_file_or_directory":
                # Only act on directories (best-effort heuristic)
                # We avoid creating known file targets like *.conf by default
                missing = err.title.split('"')[1] if '"' in err.title else None
                if not missing:
                    continue
                # Derive absolute path under root
                abs_missing = (root / missing.lstrip("/")).resolve()
                # Skip if looks like a file (has an extension)
                if abs_missing.suffix:
                    continue
                abs_missing.mkdir(parents=True, exist_ok=True)
                write_file_safely(abs_missing / ".gitkeep", "")
                console.print(f"[green]Ensured directory[/green] {abs_missing} (+ .gitkeep)")

        # YAML-based fixes for docker-compose.yml and umbrel-app.yml
        if file_path.name in ("docker-compose.yml", "docker-compose.yaml", "umbrel-app.yml"):
            try:
                content = file_path.read_text(encoding="utf-8")
                data = yaml.safe_load(content) or {}
            except Exception:
                continue

            changed = False

            if file_path.name.startswith("docker-compose") and isinstance(data, dict):
                services = data.get("services", {})
                # invalid_yaml_boolean_value -> quote booleans
                for svc_name, svc in services.items():
                    if not isinstance(svc, dict):
                        continue
                    for key in ("environment", "labels", "extra_hosts"):
                        kv = svc.get(key)
                        if isinstance(kv, dict):
                            for k, v in list(kv.items()):
                                if isinstance(v, bool):
                                    kv[k] = str(v).lower()
                                    changed = True
                    # invalid_restart_policy -> ensure on-failure (skip app_proxy)
                    if svc_name != "app_proxy":
                        if svc.get("restart") != "on-failure":
                            svc["restart"] = "on-failure"
                            changed = True
                    # invalid_container_user -> secure fix
                    if fix_secure:
                        # Never enforce user for the special app_proxy service
                        if svc_name == "app_proxy":
                            # If we previously added user: "1000:1000" by mistake, remove it
                            if svc.get("user") == "1000:1000":
                                del svc["user"]
                                changed = True
                            # Skip further user handling for app_proxy
                            continue
                        user = svc.get("user")
                        env = svc.get("environment")
                        has_uid = False
                        if isinstance(env, dict):
                            has_uid = str(env.get("UID")) == "1000" or str(env.get("PUID")) == "1000"
                        elif isinstance(env, list):
                            has_uid = any(e in ("UID=1000", "PUID=1000") for e in env)
                        # Set a non-root user if missing and no UID/PUID explicitly set
                        if (user is None or user == "root") and not has_uid:
                            svc["user"] = "1000:1000"
                            changed = True

            if file_path.name == "umbrel-app.yml":
                # Perform a minimal, line-based edit to only change the tagline line,
                # preserving the rest of the file formatting (e.g., description block styles).
                lines = content.splitlines(keepends=True)
                text_changed = False
                for i, line in enumerate(lines):
                    stripped = line.lstrip()
                    if not stripped.startswith("tagline:"):
                        continue
                    # Preserve indentation and trailing whitespace
                    indent_len = len(line) - len(stripped)
                    prefix = line[:indent_len]  # indentation
                    # Split on first ':'
                    before, _, after = stripped.partition(":")
                    value = after.strip()
                    if not value:
                        continue
                    # Preserve surrounding quotes if present
                    quote = None
                    if (value.startswith('"') and value.endswith('"') and len(value) >= 2) or (
                        value.startswith("'") and value.endswith("'") and len(value) >= 2
                    ):
                        quote = value[0]
                        inner = value[1:-1]
                    else:
                        inner = value
                    # Apply rule: remove trailing period only if exactly one period and at end
                    if inner.endswith(".") and inner.count(".") == 1:
                        inner = inner[:-1]
                        # Reconstruct line
                        new_value = f"{quote}{inner}{quote}" if quote else inner
                        lines[i] = f"{prefix}tagline: {new_value}\n"
                        text_changed = True
                    # Only modify the first tagline occurrence
                    break
                if text_changed:
                    file_path.write_text("".join(lines), encoding="utf-8")
                    console.print(f"[green]Updated[/green] {file_path}")
            else:
                if changed:
                    file_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                    console.print(f"[green]Updated[/green] {file_path}")


