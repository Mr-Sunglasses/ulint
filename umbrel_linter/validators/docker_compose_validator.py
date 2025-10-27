"""
Docker Compose validation utilities.

This module provides comprehensive validation for Docker Compose files,
including schema validation, security checks, and best practices enforcement.
"""

from __future__ import annotations

import re
from typing import Any

import jsonschema
from jsonschema import Draft7Validator

from ..core.models import FileEntry, LintingError, Severity
from .yaml_validator import parse_yaml_with_error_handling
from .docker_image_validator import DockerImageValidator
from .variable_mocker import VariableMocker

# Docker Compose JSON Schema (simplified version)
DOCKER_COMPOSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "services": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9._-]+$": {
                    "type": "object",
                    "properties": {
                        "image": {"type": "string"},
                        "user": {"type": "string"},
                        "restart": {"type": "string"},
                        "ports": {
                            "type": "array",
                            "items": {
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "number"},
                                    {"type": "object"},
                                ],
                            },
                        },
                        "volumes": {
                            "type": "array",
                            "items": {
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "object"},
                                ],
                            },
                        },
                        "environment": {
                            "oneOf": [
                                {"type": "object"},
                                {"type": "array", "items": {"type": "string"}},
                            ],
                        },
                        "labels": {
                            "oneOf": [
                                {"type": "object"},
                                {"type": "array", "items": {"type": "string"}},
                            ],
                        },
                        "extra_hosts": {
                            "oneOf": [
                                {"type": "object"},
                                {"type": "array", "items": {"type": "string"}},
                            ],
                        },
                        "network_mode": {"type": "string"},
                        "hostname": {"type": "string"},
                        "container_name": {"type": "string"},
                    },
                },
            },
        },
    },
}


class DockerComposeValidator:
    """Validator for Docker Compose files."""

    def __init__(self):
        """Initialize the validator."""
        self.schema_validator = Draft7Validator(DOCKER_COMPOSE_SCHEMA)
        self.image_validator = DockerImageValidator()
        self.variable_mocker = VariableMocker()

    async def validate_docker_compose(
        self,
        content: str,
        app_id: str,
        files: list[FileEntry],
        options: dict[str, Any] | None = None,
    ) -> list[LintingError]:
        """
        Validate a Docker Compose file.
        
        Args:
            content: Docker Compose YAML content
            app_id: ID of the app being validated
            files: List of files in the app directory
            options: Validation options
            
        Returns:
            List of linting errors
        """
        errors = []
        options = options or {}

        # Mock variables in the content
        mocked_content = self.variable_mocker.mock_variables(content)
        
        # Parse YAML
        data, parse_error = parse_yaml_with_error_handling(content, f"{app_id}/docker-compose.yml")
        if parse_error:
            return [parse_error]
        
        # Parse mocked YAML for schema validation
        mocked_data, mocked_parse_error = parse_yaml_with_error_handling(mocked_content, f"{app_id}/docker-compose.yml")
        if mocked_parse_error:
            return [mocked_parse_error]

        # Validate against JSON Schema using mocked data
        schema_errors = self._validate_schema(mocked_data, app_id)
        errors.extend(schema_errors)

        # Validate image names and architectures
        services = data.get("services", {})
        check_architectures = options.get("check_image_architectures", False)
        image_errors = await self.image_validator.validate_images(services, app_id, check_architectures)
        errors.extend(image_errors)

        # Validate boolean values using mocked data
        boolean_errors = self._validate_boolean_values(mocked_data, app_id)
        errors.extend(boolean_errors)

        # Validate volume mounts using original data (for file path checking)
        volume_errors = self._validate_volume_mounts(data, app_id, files)
        errors.extend(volume_errors)

        # Validate security settings using mocked data
        security_errors = self._validate_security_settings(mocked_data, app_id)
        errors.extend(security_errors)

        # Validate port mappings using mocked data
        port_errors = self._validate_port_mappings(mocked_data, app_id)
        errors.extend(port_errors)

        # Validate app proxy configuration using mocked data
        proxy_errors = self._validate_app_proxy_configuration(mocked_data, app_id)
        errors.extend(proxy_errors)

        # Validate restart policies using mocked data
        restart_errors = self._validate_restart_policies(mocked_data, app_id)
        errors.extend(restart_errors)

        return errors

    def _validate_schema(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate against Docker Compose JSON Schema."""
        errors = []

        try:
            self.schema_validator.validate(data)
        except jsonschema.ValidationError as e:
            error = LintingError(
                id="schema_validation_error",
                severity=Severity.ERROR,
                title="Docker Compose schema validation failed",
                message=str(e.message),
                file=f"{app_id}/docker-compose.yml",
                properties_path=e.json_path,
            )
            errors.append(error)

        return errors

    def _validate_image_names(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate Docker image names follow naming conventions."""
        errors = []
        services = data.get("services", {})

        for service_name, service_config in services.items():
            image = service_config.get("image")
            if not image:
                continue

            # Check image format: name:tag@digest
            image_match = re.match(r"^(.+):(.+)@(.+)$", image)
            if not image_match:
                errors.append(LintingError(
                    id="invalid_docker_image_name",
                    severity=Severity.ERROR,
                    title=f'Invalid image name "{image}"',
                    message='Images should be named like "<name>:<version-tag>@<sha256>"',
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.image",
                ))
            else:
                _, tag, _ = image_match.groups()
                if tag == "latest":
                    errors.append(LintingError(
                        id="invalid_docker_image_name",
                        severity=Severity.WARNING,
                        title=f'Invalid image tag "{tag}"',
                        message='Images should not use the "latest" tag',
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.image",
                    ))

        return errors

    def _validate_boolean_values(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate that boolean values are strings for Docker Compose V1 compatibility."""
        errors = []
        services = data.get("services", {})

        for service_name, service_config in services.items():
            # Check environment variables
            env = service_config.get("environment")
            if isinstance(env, dict):
                for key, value in env.items():
                    if isinstance(value, bool):
                        errors.append(LintingError(
                            id="invalid_yaml_boolean_value",
                            severity=Severity.ERROR,
                            title=f'Invalid YAML boolean value for key "{key}"',
                            message=f'Boolean values should be strings like "{str(value).lower()}" instead of {value}',
                            file=f"{app_id}/docker-compose.yml",
                            properties_path=f"services.{service_name}.environment.{key}",
                        ))

            # Check labels
            labels = service_config.get("labels")
            if isinstance(labels, dict):
                for key, value in labels.items():
                    if isinstance(value, bool):
                        errors.append(LintingError(
                            id="invalid_yaml_boolean_value",
                            severity=Severity.ERROR,
                            title=f'Invalid YAML boolean value for key "{key}"',
                            message=f'Boolean values should be strings like "{str(value).lower()}" instead of {value}',
                            file=f"{app_id}/docker-compose.yml",
                            properties_path=f"services.{service_name}.labels.{key}",
                        ))

            # Check extra_hosts
            extra_hosts = service_config.get("extra_hosts")
            if isinstance(extra_hosts, dict):
                for key, value in extra_hosts.items():
                    if isinstance(value, bool):
                        errors.append(LintingError(
                            id="invalid_yaml_boolean_value",
                            severity=Severity.ERROR,
                            title=f'Invalid YAML boolean value for key "{key}"',
                            message=f'Boolean values should be strings like "{str(value).lower()}" instead of {value}',
                            file=f"{app_id}/docker-compose.yml",
                            properties_path=f"services.{service_name}.extra_hosts.{key}",
                        ))

        return errors

    def _validate_volume_mounts(self, data: dict[str, Any], app_id: str, files: list[FileEntry]) -> list[LintingError]:
        """Validate volume mounts."""
        errors = []
        services = data.get("services", {})
        file_paths = {f.path for f in files}

        for service_name, service_config in services.items():
            volumes = service_config.get("volumes", [])

            for volume in volumes:
                if isinstance(volume, str):
                    # Check for direct APP_DATA_DIR mounting
                    if re.search(r"\$\{?APP_DATA_DIR\}?/?:", volume):
                        errors.append(LintingError(
                            id="invalid_app_data_dir_volume_mount",
                            severity=Severity.WARNING,
                            title=f'Volume "{volume}"',
                            message='Volumes should not be mounted directly into the "${APP_DATA_DIR}" directory! Please use a subdirectory like "${APP_DATA_DIR}/data" instead.',
                            file=f"{app_id}/docker-compose.yml",
                            properties_path=f"services.{service_name}.volumes",
                        ))

                    # Check for missing files/directories
                    if re.search(r"\$\{?APP_DATA_DIR\}?", volume):
                        match = re.search(r"\$\{?APP_DATA_DIR\}?/?(.*?):", volume)
                        if match:
                            relative_path = match.group(1).strip()
                            candidate_paths = {relative_path, f"{app_id}/{relative_path}"}
                            if relative_path and not (candidate_paths & file_paths):
                                errors.append(LintingError(
                                    id="missing_file_or_directory",
                                    severity=Severity.INFO,
                                    title=f'Mounted file/directory "/{app_id}/{relative_path}" doesn\'t exist',
                                    message=f'The volume "{volume}" tries to mount the file/directory "/{app_id}/{relative_path}", but it is not present. This can lead to permission errors!',
                                    file=f"{app_id}/docker-compose.yml",
                                    properties_path=f"services.{service_name}.volumes",
                                ))

                elif isinstance(volume, dict):
                    source = volume.get("source", "")
                    target = volume.get("target", "")

                    # Check for direct APP_DATA_DIR mounting
                    if re.search(r"\$\{?APP_DATA_DIR\}?/?$", source):
                        errors.append(LintingError(
                            id="invalid_app_data_dir_volume_mount",
                            severity=Severity.WARNING,
                            title=f'Volume "{source}:{target}"',
                            message='Volumes should not be mounted directly into the "${APP_DATA_DIR}" directory! Please use a subdirectory like "source: ${APP_DATA_DIR}/data" and "target: /some/dir" instead.',
                            file=f"{app_id}/docker-compose.yml",
                            properties_path=f"services.{service_name}.volumes",
                        ))

                    # Check for missing files/directories
                    if re.search(r"\$\{?APP_DATA_DIR\}?", source):
                        match = re.search(r"\$\{?APP_DATA_DIR\}?/?(.*?)$", source)
                        if match:
                            relative_path = match.group(1).strip()
                            candidate_paths = {relative_path, f"{app_id}/{relative_path}"}
                            if relative_path and not (candidate_paths & file_paths):
                                errors.append(LintingError(
                                    id="missing_file_or_directory",
                                    severity=Severity.INFO,
                                    title=f'Mounted file/directory "/{app_id}/{relative_path}" doesn\'t exist',
                                    message=f'The volume "{source}:{target}" tries to mount the file/directory "/{app_id}/{relative_path}", but it is not present. This can lead to permission errors!',
                                    file=f"{app_id}/docker-compose.yml",
                                    properties_path=f"services.{service_name}.volumes",
                                ))

        return errors

    def _validate_security_settings(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate security-related settings."""
        errors = []
        services = data.get("services", {})

        for service_name, service_config in services.items():
            # Check for Docker socket mounting
            volumes = service_config.get("volumes", [])
            for volume in volumes:
                if isinstance(volume, str) and "/var/run/docker.sock" in volume:
                    errors.append(LintingError(
                        id="docker_socket_mount",
                        severity=Severity.WARNING,
                        title=f'Docker socket is mounted in "{service_name}"',
                        message=f'The volume "{volume}" mounts the Docker socket, which can be a security risk. Consider using docker-in-docker instead (see portainer as an example).',
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.volumes",
                    ))
                elif isinstance(volume, dict) and "/var/run/docker.sock" in volume.get("source", ""):
                    errors.append(LintingError(
                        id="docker_socket_mount",
                        severity=Severity.WARNING,
                        title=f'Docker socket is mounted in "{service_name}"',
                        message=f'The volume "{volume.get("source")}:{volume.get("target")}" mounts the Docker socket, which can be a security risk. Consider using docker-in-docker instead (see portainer as an example).',
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.volumes",
                    ))

            # Check for root user usage
            user = service_config.get("user")
            environment = service_config.get("environment", {})

            # Check for UID/PUID environment variables
            has_uid_env = False
            if isinstance(environment, dict):
                for key, value in environment.items():
                    if key in ["UID", "PUID"] and str(value) == "1000":
                        has_uid_env = True
                        break
            elif isinstance(environment, list):
                for env_var in environment:
                    if "=" in env_var:
                        key, value = env_var.split("=", 1)
                        if key in ["UID", "PUID"] and value == "1000":
                            has_uid_env = True
                            break

            # Skip user validation for app_proxy service as it needs root privileges
            if service_name == "app_proxy":
                continue

            if user == "root":
                errors.append(LintingError(
                    id="invalid_container_user",
                    severity=Severity.INFO,
                    title=f'Using unsafe user "{user}" in service "{service_name}"',
                    message=f'The user "{user}" can lead to security vulnerabilities. If possible please use a non-root user instead.',
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.user",
                ))
            elif not user and not has_uid_env:
                errors.append(LintingError(
                    id="invalid_container_user",
                    severity=Severity.INFO,
                    title=f'Potentially using unsafe user in service "{service_name}"',
                    message='The default container user "root" can lead to security vulnerabilities. If you are using the root user, please try to specify a different user (e.g. "1000:1000") in the compose file or try to set the UID/PUID and GID/PGID environment variables to 1000.',
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.user",
                ))

            # Check for host network mode
            network_mode = service_config.get("network_mode")
            if network_mode == "host":
                errors.append(LintingError(
                    id="container_network_mode_host",
                    severity=Severity.INFO,
                    title=f'Service "{service_name}" uses host network mode',
                    message="The host network mode can lead to security vulnerabilities. If possible please use the default bridge network mode and expose the necessary ports.",
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.network_mode",
                ))

        return errors

    def _validate_port_mappings(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate port mappings."""
        errors = []
        services = data.get("services", {})

        for service_name, service_config in services.items():
            ports = service_config.get("ports", [])

            for port in ports:
                if isinstance(port, (str, int)):
                    errors.append(LintingError(
                        id="external_port_mapping",
                        severity=Severity.INFO,
                        title=f'External port mapping "{port}"',
                        message="Port mappings may be unnecessary for the app to function correctly. Docker's internal DNS resolves container names to IP addresses within the same network. External access to the web interface is handled by the app_proxy container. Port mappings are only needed if external access is required to a port not proxied by the app_proxy, or if an app needs to expose multiple ports for its functionality (e.g., DHCP, DNS, P2P, etc.).",
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.ports",
                    ))
                elif isinstance(port, dict):
                    target = port.get("target")
                    published = port.get("published")
                    port_str = f"{target}{f':{published}' if published else ''}"
                    errors.append(LintingError(
                        id="external_port_mapping",
                        severity=Severity.INFO,
                        title=f'External port mapping "{port_str}"',
                        message="Port mappings may be unnecessary for the app to function correctly. Docker's internal DNS resolves container names to IP addresses within the same network. External access to the web interface is handled by the app_proxy container. Port mappings are only needed if external access is required to a port not proxied by the app_proxy, or if an app needs to expose multiple ports for its functionality (e.g., DHCP, DNS, P2P, etc.).",
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.ports",
                    ))

        return errors

    def _validate_app_proxy_configuration(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate app_proxy configuration."""
        errors = []
        services = data.get("services", {})

        # Collect hostnames from all services
        hostnames = set()
        for service_name, service_config in services.items():
            if service_name == "app_proxy":
                continue

            hostname = service_config.get("hostname")
            if hostname:
                hostnames.add(hostname)

            container_name = service_config.get("container_name")
            if container_name:
                hostnames.add(container_name)

        # Validate app_proxy service
        app_proxy = services.get("app_proxy")
        if app_proxy:
            environment = app_proxy.get("environment", {})
            env_vars = {}

            if isinstance(environment, dict):
                env_vars = environment
            elif isinstance(environment, list):
                for env_var in environment:
                    if "=" in env_var:
                        key, value = env_var.split("=", 1)
                        env_vars[key] = value

            # Check APP_HOST
            if "APP_HOST" not in env_vars:
                errors.append(LintingError(
                    id="invalid_app_proxy_configuration",
                    severity=Severity.ERROR,
                    title="Missing APP_HOST environment variable",
                    message='The app_proxy container needs to have the APP_HOST environment variable set to the hostname of the app_proxy container (e.g. "<app-id>_<web-container-name>_1").',
                    file=f"{app_id}/docker-compose.yml",
                    properties_path="services.app_proxy.environment",
                ))
            else:
                app_host = str(env_vars["APP_HOST"])
                if not app_host.startswith("$") and app_host not in hostnames:
                    parts = app_host.split("_")
                    if len(parts) >= 3:
                        appid, container_name, number = parts[0], parts[1], parts[2]
                        if (appid != app_id.lower() or
                            container_name not in [s for s in services.keys() if s != "app_proxy"] or
                            number != "1"):
                            errors.append(LintingError(
                                id="invalid_app_proxy_configuration",
                                severity=Severity.WARNING,
                                title="Invalid APP_HOST environment variable",
                                message='The APP_HOST environment variable must be set to the hostname of the app_proxy container (e.g. "<app-id>_<web-container-name>_1").',
                                file=f"{app_id}/docker-compose.yml",
                                properties_path="services.app_proxy.environment",
                            ))

            # Check APP_PORT
            if "APP_PORT" not in env_vars:
                errors.append(LintingError(
                    id="invalid_app_proxy_configuration",
                    severity=Severity.ERROR,
                    title="Missing APP_PORT environment variable",
                    message="The app_proxy container needs to have the APP_PORT environment variable set to the port the ui of the app inside the container is listening on.",
                    file=f"{app_id}/docker-compose.yml",
                    properties_path="services.app_proxy.environment",
                ))
            else:
                app_port = str(env_vars["APP_PORT"])
                if not app_port.startswith("$") and not app_port.isdigit():
                    errors.append(LintingError(
                        id="invalid_app_proxy_configuration",
                        severity=Severity.WARNING,
                        title="Invalid APP_PORT environment variable",
                        message="The APP_PORT environment variable must be set to the port the ui of the app inside the container is listening on.",
                        file=f"{app_id}/docker-compose.yml",
                        properties_path="services.app_proxy.environment",
                    ))

        return errors

    def _validate_restart_policies(self, data: dict[str, Any], app_id: str) -> list[LintingError]:
        """Validate restart policies."""
        errors = []
        services = data.get("services", {})

        for service_name, service_config in services.items():
            if service_name == "app_proxy":
                continue

            restart = service_config.get("restart")
            # Warn when restart is missing or not set to on-failure
            if restart != "on-failure":
                errors.append(LintingError(
                    id="invalid_restart_policy",
                    severity=Severity.WARNING,
                    title="Invalid restart policy",
                    message=f'The restart policy of the container "{service_name}" should be set to "on-failure".',
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.restart",
                ))

        return errors
