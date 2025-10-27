"""
Docker image validation utilities.

This module provides comprehensive validation for Docker images,
including registry API calls and architecture checking.
"""

from __future__ import annotations

import re
from typing import Any
import httpx
from urllib.parse import urlparse

from ..core.models import LintingError, Severity


class DockerImage:
    """Represents a Docker image with parsing and validation capabilities."""
    
    def __init__(self, host: str, path: str, tag: str | None = None, digest: str | None = None):
        """Initialize a Docker image."""
        self.host = host
        self.path = path
        self.tag = tag
        self.digest = digest
    
    @classmethod
    def from_string(cls, image_string: str) -> DockerImage:
        """Parse a Docker image string into components."""
        # Handle different image formats
        # Format: [registry/]namespace/image:tag@digest
        # Examples:
        # - docker.io/library/nginx:latest
        # - nginx:latest
        # - nginx:latest@sha256:abc123
        # - registry.example.com/myapp:1.0.0@sha256:abc123
        
        # Check for digest
        if "@" in image_string:
            image_part, digest = image_string.rsplit("@", 1)
        else:
            image_part = image_string
            digest = None
        
        # Check for tag
        if ":" in image_part:
            name_part, tag = image_part.rsplit(":", 1)
        else:
            name_part = image_part
            tag = None
        
        # Parse registry and path
        parts = name_part.split("/")
        if len(parts) == 1:
            # Single name like "nginx" -> docker.io/library/nginx
            host = "docker.io"
            path = f"library/{parts[0]}"
        elif len(parts) == 2:
            # Two parts like "nginx/nginx" or "registry.com/app"
            if "." in parts[0] or ":" in parts[0]:
                # First part looks like a registry
                host = parts[0]
                path = parts[1]
            else:
                # Two-part namespace
                host = "docker.io"
                path = "/".join(parts)
        else:
            # Multiple parts like "registry.com/namespace/app"
            host = parts[0]
            path = "/".join(parts[1:])
        
        return cls(host=host, path=path, tag=tag, digest=digest)
    
    def __str__(self) -> str:
        """String representation of the image."""
        result = f"{self.host}/{self.path}"
        if self.tag:
            result += f":{self.tag}"
        if self.digest:
            result += f"@{self.digest}"
        return result
    
    @property
    def api_host(self) -> str:
        """Get the API host for registry calls."""
        # Docker Hub API is served from registry-1.docker.io
        if self.host in {"docker.io", "www.docker.com"}:
            return "registry-1.docker.io"
        return self.host
    
    @property
    def api_path(self) -> str:
        """Get the API path for registry calls."""
        return self.path


class DockerRegistryClient:
    """Client for Docker registry API calls."""
    
    def __init__(self, timeout: float = 1.0):
        """Initialize the registry client."""
        self.timeout = timeout
        self._cache: dict[str, bool] = {}
    
    async def is_registry(self, host: str) -> bool:
        """Check if a host is a valid Docker registry."""
        if host in self._cache:
            return self._cache[host]
        
        # Special cases for well-known registries
        if host in {"docker.io", "registry-1.docker.io", "ghcr.io"}:
            self._cache[host] = True
            return True
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(f"https://{host}/v2/")
                # Per Docker Registry HTTP API V2 spec, registries may return 200 (OK)
                # or 401 (Unauthorized) for /v2/ endpoint, while still being valid.
                is_registry = False
                if response.status_code in (200, 401):
                    is_registry = True
                # Some registries set explicit header
                if response.headers.get("Docker-Distribution-Api-Version") == "registry/2.0":
                    is_registry = True
                self._cache[host] = is_registry
                return is_registry
        except Exception:
            self._cache[host] = False
            return False
    
    async def get_architectures(self, image: DockerImage) -> list[dict[str, str]]:
        """Get supported architectures for a Docker image."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                # Get manifest
                ref = image.digest or image.tag or "latest"
                manifest_url = f"https://{image.api_host}/v2/{image.api_path}/manifests/{ref}"
                accept = (
                    "application/vnd.oci.image.manifest.v1+json, "
                    "application/vnd.oci.image.index.v1+json, "
                    "application/vnd.docker.distribution.manifest.v2+json, "
                    "application/vnd.docker.distribution.manifest.list.v2+json"
                )
                headers = {"Accept": accept}

                response = await client.get(manifest_url, headers=headers)

                # Handle auth challenge (e.g., ghcr.io returns 401 with WWW-Authenticate)
                if response.status_code == 401:
                    www_auth = response.headers.get("WWW-Authenticate", "")
                    params = self._parse_www_authenticate(www_auth)
                    realm = params.get("realm")
                    if realm:
                        # scope: repository:<name>:pull
                        scope = params.get("scope") or f"repository:{image.api_path}:pull"
                        service = params.get("service")
                        token_params = {"scope": scope}
                        if service:
                            token_params["service"] = service
                        token_resp = await client.get(realm, params=token_params, headers={"Accept": "application/json"})
                        if token_resp.status_code == 200:
                            token = token_resp.json().get("token") or token_resp.json().get("access_token")
                            if token:
                                headers["Authorization"] = f"Bearer {token}"
                                response = await client.get(manifest_url, headers=headers)

                response.raise_for_status()

                manifest = response.json()
                content_type = response.headers.get("Content-Type", "")

                # Parse architectures based on manifest type
                if "manifest.list" in content_type or "image.index" in content_type or manifest.get("manifests"):
                    # Multi-arch manifest
                    architectures = []
                    for manifest_ref in manifest.get("manifests", []):
                        platform = manifest_ref.get("platform", {})
                        architectures.append({
                            "os": platform.get("os", "linux"),
                            "architecture": platform.get("architecture", "amd64"),
                            "variant": platform.get("variant")
                        })
                    return architectures
                else:
                    # Single-arch manifest
                    return [{"os": "linux", "architecture": "amd64"}]

        except httpx.HTTPStatusError as e:
            # Propagate status code info up
            raise Exception(f"{e.response.status_code} {e.response.reason_phrase}")
        except Exception as e:
            raise Exception(f"Failed to get architectures for {image}: {e}")

    def _parse_www_authenticate(self, header: str) -> dict:
        params: dict[str, str] = {}
        if not header:
            return params
        # Format: Bearer realm="...",service="...",scope="..."
        try:
            parts = header.split(" ", 1)
            if len(parts) == 2:
                for item in parts[1].split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        params[k.strip()] = v.strip().strip('"')
        except Exception:
            pass
        return params
    
    async def validate_image(self, image: DockerImage) -> list[LintingError]:
        """Validate a Docker image and return any errors."""
        errors = []
        
        # Check if it's a valid registry
        if not await self.is_registry(image.api_host):
            errors.append(LintingError(
                id="invalid_docker_image_name",
                severity=Severity.ERROR,
                title=f'Invalid registry "{image.api_host}"',
                message=f'The registry "{image.api_host}" is not a valid Docker registry',
                file="docker-compose.yml",
                properties_path="services.image"
            ))
            return errors
        
        try:
            # Get architectures
            architectures = await self.get_architectures(image)
            
            # Check if it supports both arm64 and amd64
            has_arm64 = any(
                arch.get("os") == "linux" and arch.get("architecture") == "arm64"
                for arch in architectures
            )
            has_amd64 = any(
                arch.get("os") == "linux" and arch.get("architecture") == "amd64"
                for arch in architectures
            )
            
            if not (has_arm64 and has_amd64):
                errors.append(LintingError(
                    id="invalid_image_architectures",
                    severity=Severity.ERROR,
                    title=f'Invalid image architectures for image "{image}"',
                    message=f'The image "{image}" does not support the architectures "arm64" and "amd64". Please make sure that the image supports both architectures.',
                    file="docker-compose.yml",
                    properties_path="services.image"
                ))
                
        except Exception as e:
            message = str(e)
            # If we cannot authenticate to fetch manifest (e.g., 401), do not fail hard
            if "401" in message or "Unauthorized" in message:
                errors.append(LintingError(
                    id="image_architecture_unverified",
                    severity=Severity.INFO,
                    title=f'Could not verify architectures for image "{image}"',
                    message="The registry requires authentication to inspect the image manifest. Skipping architecture verification.",
                    file="docker-compose.yml",
                    properties_path="services.image"
                ))
            else:
                errors.append(LintingError(
                    id="invalid_docker_image_name",
                    severity=Severity.ERROR,
                    title=f'Invalid image name "{image}"',
                    message=message,
                    file="docker-compose.yml",
                    properties_path="services.image"
                ))
        
        return errors


class DockerImageValidator:
    """Validator for Docker images with registry integration."""
    
    def __init__(self):
        """Initialize the validator."""
        self.registry_client = DockerRegistryClient()
    
    async def validate_images(self, services: dict[str, Any], app_id: str, check_architectures: bool = False) -> list[LintingError]:
        """Validate Docker images in services."""
        errors = []
        
        for service_name, service_config in services.items():
            image_string = service_config.get("image")
            if not image_string:
                continue
            
            # Parse image
            try:
                image = DockerImage.from_string(image_string)
            except Exception as e:
                errors.append(LintingError(
                    id="invalid_docker_image_name",
                    severity=Severity.ERROR,
                    title=f'Invalid image name "{image_string}"',
                    message=str(e),
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.image"
                ))
                continue
            
            # Enforce image format with immutable digest: <name>:<tag>@sha256:<64-hex>
            # This avoids mutable tags and ensures reproducible pulls.
            if not re.match(r"^[a-zA-Z0-9./:_-]+:[^@]+@sha256:[0-9a-fA-F]{64}$", image_string):
                errors.append(LintingError(
                    id="invalid_docker_image_name",
                    severity=Severity.ERROR,
                    title=f'Invalid image name "{image_string}"',
                    message='Images must include an immutable digest: "<name>:<version-tag>@sha256:<64-hex>"',
                    file=f"{app_id}/docker-compose.yml",
                    properties_path=f"services.{service_name}.image"
                ))
            else:
                # Check for "latest" tag
                if image.tag == "latest":
                    errors.append(LintingError(
                        id="invalid_docker_image_name",
                        severity=Severity.WARNING,
                        title=f'Invalid image tag "{image.tag}"',
                        message='Images should not use the "latest" tag',
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.image"
                    ))
            
            # Check architectures if requested
            if check_architectures:
                try:
                    image_errors = await self.registry_client.validate_image(image)
                    # Update file paths for the specific service
                    for error in image_errors:
                        error.file = f"{app_id}/docker-compose.yml"
                        error.properties_path = f"services.{service_name}.image"
                    errors.extend(image_errors)
                except Exception as e:
                    errors.append(LintingError(
                        id="invalid_docker_image_name",
                        severity=Severity.ERROR,
                        title=f'Failed to validate image "{image_string}"',
                        message=str(e),
                        file=f"{app_id}/docker-compose.yml",
                        properties_path=f"services.{service_name}.image"
                    ))
        
        return errors
