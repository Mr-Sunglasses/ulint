"""
Main linter implementation.

This module provides the core UmbrelLinter class that orchestrates
all linting operations for Umbrel applications and app stores.
"""

from __future__ import annotations

from pathlib import Path

from ..schemas.umbrel_app import UmbrelAppManifest, UmbrelAppStoreManifest
from ..utils.filesystem import file_exists, get_directory_files
from ..validators.docker_compose_validator import DockerComposeValidator
from ..validators.github_validator import GitHubValidator
from ..validators.yaml_validator import parse_yaml_with_error_handling
from .models import (
    FileEntry,
    LinterConfig,
    LintingContext,
    LintingError,
    LintingResult,
    Severity,
)


class UmbrelLinter:
    """
    Main linter class for Umbrel applications and app stores.
    
    This class provides comprehensive linting capabilities including:
    - YAML validation for app manifests
    - Docker Compose validation
    - Directory structure validation
    - Security and best practices checks
    """

    def __init__(self, config: LinterConfig | None = None):
        """
        Initialize the linter.
        
        Args:
            config: Optional linter configuration
        """
        self.config = config or LinterConfig()
        self.docker_compose_validator = DockerComposeValidator()
        self.github_validator = GitHubValidator()

    def lint_app_store(self, directory: Path, context: LintingContext | None = None) -> LintingResult:
        """
        Lint an Umbrel app store.
        
        Args:
            directory: Path to the app store directory
            context: Optional linting context
            
        Returns:
            Linting result with all errors found
        """
        result = LintingResult()
        context = context or LintingContext()

        # Check for umbrel-app-store.yml
        store_manifest_path = directory / "umbrel-app-store.yml"
        if not file_exists(store_manifest_path):
            if context.app_store_type == "community":
                result.add_error(LintingError(
                    id="missing_umbrel_app_store_yml",
                    severity=Severity.ERROR,
                    title="umbrel-app-store.yml does not exist",
                    message="For community app stores, the file umbrel-app-store.yml is required",
                    file="umbrel-app-store.yml",
                ))
        else:
            # Validate umbrel-app-store.yml
            store_errors = self._validate_app_store_manifest(store_manifest_path)
            for error in store_errors:
                result.add_error(error)

        # Check for README.md
        readme_path = directory / "README.md"
        if not file_exists(readme_path):
            result.add_error(LintingError(
                id="missing_readme",
                severity=Severity.WARNING,
                title="README.md does not exist",
                message="A README.md file is highly recommended to tell users, how to install your App Store and what apps are available",
                file="README.md",
            ))

        return result

    async def lint_app(self, directory: Path, app_id: str, context: LintingContext | None = None) -> LintingResult:
        """
        Lint a single Umbrel app.
        
        Args:
            directory: Path to the app directory
            app_id: ID of the app to lint
            context: Optional linting context
            
        Returns:
            Linting result with all errors found
        """
        result = LintingResult()
        context = context or LintingContext()
        context.app_id = app_id

        app_directory = directory / app_id
        if not app_directory.exists():
            result.add_error(LintingError(
                id="app_directory_not_found",
                severity=Severity.ERROR,
                title=f"App directory not found: {app_id}",
                message=f"App with id {app_id} does not exist",
                file=app_id,
            ))
            return result

        # Get all files in the app directory
        files = get_directory_files(app_directory)

        # Validate umbrel-app.yml
        manifest_errors = await self._validate_app_manifest(app_directory / "umbrel-app.yml", app_id, context)
        for error in manifest_errors:
            result.add_error(error)

        # Validate docker-compose.yml
        compose_errors = await self._validate_docker_compose(
            app_directory / "docker-compose.yml",
            app_id,
            files,
            context,
        )
        for error in compose_errors:
            result.add_error(error)

        # Validate directory structure
        structure_errors = self._validate_directory_structure(files)
        for error in structure_errors:
            result.add_error(error)

        return result

    async def lint_all_apps(self, directory: Path, context: LintingContext | None = None) -> LintingResult:
        """
        Lint all apps in a directory.
        
        Args:
            directory: Path to the directory containing apps
            context: Optional linting context
            
        Returns:
            Combined linting result for all apps
        """
        result = LintingResult()
        context = context or LintingContext()

        # Check if this directory itself is an app (contains umbrel-app.yml)
        if (directory / "umbrel-app.yml").exists():
            # This is a single app directory, not an app store
            # Get the app ID from the directory name
            app_id = directory.name
            app_result = await self.lint_app(directory.parent, app_id, context)
            return app_result

        # First lint the app store itself
        store_result = self.lint_app_store(directory, context)
        result.errors.extend(store_result.errors)
        result.success = result.success and store_result.success

        # Find all app directories
        app_directories = []
        for item in directory.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check if it's an app directory by looking for umbrel-app.yml
                if (item / "umbrel-app.yml").exists():
                    app_directories.append(item.name)

        # Lint each app
        for app_id in app_directories:
            app_result = await self.lint_app(directory, app_id, context)
            result.errors.extend(app_result.errors)
            result.success = result.success and app_result.success

        return result

    def _validate_app_store_manifest(self, manifest_path: Path) -> list[LintingError]:
        """Validate umbrel-app-store.yml manifest."""
        errors = []

        try:
            with open(manifest_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            errors.append(LintingError(
                id="file_read_error",
                severity=Severity.ERROR,
                title="Failed to read umbrel-app-store.yml",
                message=str(e),
                file=str(manifest_path),
            ))
            return errors

        # Parse YAML
        data, parse_error = parse_yaml_with_error_handling(content, "umbrel-app-store.yml")
        if parse_error:
            errors.append(parse_error)
            return errors

        # Validate with Pydantic schema
        try:
            UmbrelAppStoreManifest(**data)
        except Exception as e:
            errors.append(LintingError(
                id="schema_validation_error",
                severity=Severity.ERROR,
                title="umbrel-app-store.yml validation failed",
                message=str(e),
                file="umbrel-app-store.yml",
            ))

        return errors

    async def _validate_app_manifest(self, manifest_path: Path, app_id: str, context: LintingContext) -> list[LintingError]:
        """Validate umbrel-app.yml manifest."""
        errors = []

        if not file_exists(manifest_path):
            errors.append(LintingError(
                id="missing_umbrel_app_yml",
                severity=Severity.ERROR,
                title="umbrel-app.yml does not exist",
                message='Every app needs a manifest file called "umbrel-app.yml" at the root of the app directory',
                file=f"{app_id}/umbrel-app.yml",
            ))
            return errors

        try:
            with open(manifest_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            errors.append(LintingError(
                id="file_read_error",
                severity=Severity.ERROR,
                title="Failed to read umbrel-app.yml",
                message=str(e),
                file=f"{app_id}/umbrel-app.yml",
            ))
            return errors

        # Parse YAML
        data, parse_error = parse_yaml_with_error_handling(content, f"{app_id}/umbrel-app.yml")
        if parse_error:
            errors.append(parse_error)
            return errors

        # Validate GitHub URLs (submission and repo) first
        github_errors = await self.github_validator.validate_github_urls(data, app_id)
        errors.extend(github_errors)

        # Validate with Pydantic schema
        try:
            manifest = UmbrelAppManifest(**data)
        except Exception as e:
            # Parse Pydantic validation errors for better formatting
            error_message = str(e)
            
            # Try to extract field name and error from Pydantic error
            if "validation error" in error_message.lower():
                lines = error_message.split('\n')
                field_name = None
                error_detail = None
                
                # Parse the error message to extract field and error
                for i, line in enumerate(lines):
                    line = line.strip()
                    # Skip header lines
                    if "validation error" in line.lower() or not line:
                        continue
                    # Look for field name (lines without "For further information")
                    if not line.startswith("For further information") and not any(keyword in line.lower() for keyword in ["input should", "field required", "value error"]):
                        if not field_name:
                            field_name = line
                    # Look for error detail
                    elif any(keyword in line.lower() for keyword in ["input should", "field required", "value error"]):
                        error_detail = line
                        break
                
                # Create user-friendly error message
                if field_name and error_detail:
                    # Handle specific error types
                    if "tagline" in error_message.lower() and "period" in error_message.lower():
                        title = "Invalid tagline"
                        message = "Taglines should not end with a period"
                    elif "input should be a valid string" in error_detail.lower():
                        title = f'Invalid field "{field_name}"'
                        message = f'The field "{field_name}" must be a string, but received an invalid value'
                    elif "field required" in error_detail.lower():
                        title = f'Missing required field "{field_name}"'
                        message = f'The required field "{field_name}" is missing'
                    else:
                        title = f'Invalid field "{field_name}"'
                        message = error_detail
                    
                    errors.append(LintingError(
                        id="schema_validation_error",
                        severity=Severity.ERROR,
                        title=title,
                        message=message,
                        file=f"{app_id}/umbrel-app.yml",
                        properties_path=field_name if field_name else None,
                    ))
                else:
                    # Fallback to generic error
                    errors.append(LintingError(
                        id="schema_validation_error",
                        severity=Severity.ERROR,
                        title="umbrel-app.yml validation failed",
                        message=error_message,
                        file=f"{app_id}/umbrel-app.yml",
                    ))
            else:
                # Non-Pydantic error
                errors.append(LintingError(
                    id="schema_validation_error",
                    severity=Severity.ERROR,
                    title="umbrel-app.yml validation failed",
                    message=error_message,
                    file=f"{app_id}/umbrel-app.yml",
                ))
            # Don't return early - continue with other validations
            manifest = None

        # Additional validations for new submissions (only if manifest is valid)
        if context.is_new_submission and manifest is not None:
            # Check submission field matches PR URL
            if context.pull_request_url and manifest.submission != context.pull_request_url:
                errors.append(LintingError(
                    id="invalid_submission_field",
                    severity=Severity.ERROR,
                    title=f'Invalid submission field "{manifest.submission}"',
                    message=f"The submission field must be set to the URL of this pull request: {context.pull_request_url}",
                    file=f"{app_id}/umbrel-app.yml",
                    properties_path="submission",
                ))

            # Check release notes are empty for new submissions
            if manifest.releaseNotes and len(manifest.releaseNotes) > 0:
                errors.append(LintingError(
                    id="filled_out_release_notes_on_first_submission",
                    severity=Severity.ERROR,
                    title='"releaseNotes" needs to be empty for new app submissions',
                    message='The "releaseNotes" field must be empty for new app submissions as it is being displayed to the user only in case of an update.',
                    file=f"{app_id}/umbrel-app.yml",
                    properties_path="releaseNotes",
                ))

            # Check icon and gallery are empty for new submissions
            if manifest.icon or (manifest.gallery and len(manifest.gallery) > 0):
                errors.append(LintingError(
                    id="filled_out_icon_or_gallery_on_first_submission",
                    severity=Severity.WARNING,
                    title='"icon" and "gallery" needs to be empty for new app submissions',
                    message='The "icon" and "gallery" fields must be empty for new app submissions as it is being created by the Umbrel team.',
                    file=f"{app_id}/umbrel-app.yml",
                    properties_path="icon" if manifest.icon else "gallery",
                ))

        # Check for duplicate ports
        if context.all_app_manifests:
            used_ports = self._get_used_ports(context.all_app_manifests, app_id)
            if manifest.port in used_ports:
                app_name = used_ports[manifest.port]
                errors.append(LintingError(
                    id="duplicate_ui_port",
                    severity=Severity.ERROR,
                    title=f"Port {manifest.port} is already used by {app_name}",
                    message="Each app must use a unique port",
                    file=f"{app_id}/umbrel-app.yml",
                    properties_path="port",
                ))

        return errors

    async def _validate_docker_compose(self, compose_path: Path, app_id: str, files: list[FileEntry], context: LintingContext) -> list[LintingError]:
        """Validate docker-compose.yml file."""
        errors = []

        if not file_exists(compose_path):
            errors.append(LintingError(
                id="missing_docker_compose_yml",
                severity=Severity.ERROR,
                title="docker-compose.yml does not exist",
                message='Every app needs a docker compose file called "docker-compose.yml" at the root of the app directory',
                file=f"{app_id}/docker-compose.yml",
            ))
            return errors

        try:
            with open(compose_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            errors.append(LintingError(
                id="file_read_error",
                severity=Severity.ERROR,
                title="Failed to read docker-compose.yml",
                message=str(e),
                file=f"{app_id}/docker-compose.yml",
            ))
            return errors

        # Use Docker Compose validator
        options = {
            "check_image_architectures": self.config.check_image_architectures,
        }

        compose_errors = await self.docker_compose_validator.validate_docker_compose(
            content, app_id, files, options,
        )
        errors.extend(compose_errors)

        return errors

    def _validate_directory_structure(self, files: list[FileEntry]) -> list[LintingError]:
        """Validate directory structure."""
        errors = []

        # Find empty directories (no .gitkeep file)
        directories = {f.path for f in files if f.type == "directory"}
        files_set = {f.path for f in files if f.type == "file"}

        for directory in directories:
            # Check if directory has any files or subdirectories
            has_content = any(
                f.path.startswith(directory + "/") for f in files
            )

            if not has_content:
                errors.append(LintingError(
                    id="empty_app_data_directory",
                    severity=Severity.ERROR,
                    title=f'Empty directory "{directory}"',
                    message=f'Please add a ".gitkeep" file to the directory "{directory}". This is necessary to ensure the correct permissions of the directory after cloning!',
                    file=directory,
                ))

        return errors

    def _get_used_ports(self, all_manifests: list[str], current_app_id: str) -> dict[int, str]:
        """Get used ports from all app manifests."""
        used_ports = {}

        for manifest_content in all_manifests:
            data, _ = parse_yaml_with_error_handling(manifest_content, "manifest")
            if data and isinstance(data, dict):
                app_id = data.get("id")
                name = data.get("name")
                port = data.get("port")

                if app_id and name and port and app_id != current_app_id:
                    # Ensure port is an integer
                    try:
                        port_int = int(port)
                        used_ports[port_int] = f"{name} ({app_id})"
                    except (ValueError, TypeError):
                        # Skip invalid port values
                        continue

        return used_ports
