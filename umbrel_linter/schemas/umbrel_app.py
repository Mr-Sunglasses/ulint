"""
Schema definitions for umbrel-app.yml validation.

This module defines Pydantic models for validating Umbrel app manifest files,
ensuring they conform to the expected structure and requirements.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, validator


class UmbrelAppManifest(BaseModel):
    """Schema for umbrel-app.yml manifest files."""

    # Required fields
    manifestVersion: float | int = Field(
        ...,
        description="Manifest version (1, 1.1, or 1.2)",
        ge=1,
        le=2,
    )
    id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique identifier for the app",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Display name of the app",
    )
    tagline: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Short tagline for the app",
    )
    category: str = Field(
        ...,
        description="Category of the app",
    )
    version: str = Field(
        ...,
        min_length=1,
        description="Version of the app",
    )
    port: int = Field(
        ...,
        ge=0,
        le=65535,
        description="Port number for the app",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Detailed description of the app",
    )
    developer: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Name of the developer",
    )
    submitter: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Name of the submitter",
    )
    
    @validator("developer", "submitter", pre=True)
    def convert_to_string(cls, v):
        """Convert numeric values to strings for developer and submitter fields."""
        if isinstance(v, (int, float)):
            return str(v)
        return v
    submission: HttpUrl = Field(
        ...,
        description="URL of the submission (usually a pull request)",
    )
    support: HttpUrl = Field(
        ...,
        description="Support URL for the app",
    )
    website: HttpUrl = Field(
        ...,
        description="Website URL for the app",
    )
    path: str = Field(
        ...,
        description="Path for the app (can be empty string)",
    )

    # Optional fields
    disabled: bool | None = Field(None, description="Whether the app is disabled")
    icon: str | None = Field(None, description="Icon URL for the app")
    gallery: list[str] = Field(default_factory=list, description="Gallery images")
    releaseNotes: str | None = Field(
        None,
        min_length=0,
        max_length=5000,
        description="Release notes for the app",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of app dependencies",
    )
    permissions: list[str] | None = Field(
        None,
        description="Required permissions (STORAGE_DOWNLOADS, GPU)",
    )
    defaultUsername: str | None = Field(
        None,
        description="Default username for the app",
    )
    defaultPassword: str | None = Field(
        None,
        description="Default password for the app",
    )
    deterministicPassword: bool | None = Field(
        None,
        description="Whether to use deterministic password",
    )
    optimizedForUmbrelHome: bool | None = Field(
        None,
        description="Whether optimized for Umbrel Home",
    )
    torOnly: bool | None = Field(
        None,
        description="Whether the app is Tor-only",
    )
    installSize: int | None = Field(
        None,
        ge=0,
        description="Install size in bytes",
    )
    widgets: list[dict] | None = Field(
        None,
        description="Widget configurations",
    )
    defaultShell: str | None = Field(
        None,
        description="Default shell for the app",
    )
    backupIgnore: list[str] | None = Field(
        None,
        description="Files to ignore during backup",
    )
    repo: HttpUrl | str | None = Field(
        None,
        description="Repository URL (can be empty string)",
    )

    @validator("manifestVersion")
    def validate_manifest_version(cls, v):
        """Validate manifest version is supported."""
        if v not in [1, 1.1, 1.2]:
            raise ValueError("manifestVersion must be 1, 1.1, or 1.2")
        return v

    @validator("id")
    def validate_id(cls, v):
        """Validate app ID doesn't start with reserved prefix."""
        if v.startswith("umbrel-app-store"):
            raise ValueError(
                "The id of the app can't start with 'umbrel-app-store' as it is the id of the app repository",
            )
        return v

    @validator("tagline")
    def validate_tagline(cls, v):
        """Validate tagline doesn't end with period."""
        if v.endswith(".") and v.count(".") == 1:
            raise ValueError("Taglines should not end with a period")
        return v

    @validator("category")
    def validate_category(cls, v):
        """Validate category is from allowed list."""
        allowed_categories = [
            "files", "bitcoin", "media", "networking", "social",
            "automation", "finance", "ai", "developer",
        ]
        if v not in allowed_categories:
            raise ValueError(f'category must be one of: {", ".join(allowed_categories)}')
        return v

    @validator("permissions")
    def validate_permissions(cls, v):
        """Validate permissions are from allowed list."""
        if v is not None:
            allowed_permissions = ["STORAGE_DOWNLOADS", "GPU"]
            for perm in v:
                if perm not in allowed_permissions:
                    raise ValueError(f'permission must be one of: {", ".join(allowed_permissions)}')
        return v

    @validator("dependencies")
    def validate_dependencies(cls, v, values):
        """Validate dependencies don't include self."""
        if "id" in values and values["id"] in v:
            raise ValueError("Dependencies can't include its own app id")
        return v

    @validator("path")
    def validate_path(cls, v):
        """Validate path is a valid URL path (can be empty)."""
        # Path can be empty string according to TypeScript schema
        if v and not v.startswith("/"):
            raise ValueError("path must start with /")
        return v

    @validator("repo")
    def validate_repo(cls, v):
        """Validate repo is either empty string or valid URL."""
        if v == "":
            return v
        return v


class UmbrelAppStoreManifest(BaseModel):
    """Schema for umbrel-app-store.yml manifest files."""

    id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique identifier for the app store",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Display name of the app store",
    )

    @validator("id")
    def validate_id(cls, v):
        """Validate app store ID format and restrictions."""
        if v.startswith("umbrel-app-store"):
            raise ValueError(
                "The id of the app can't start with 'umbrel-app-store' as it is the id of the official Umbrel App Store.",
            )

        # Check format: only lowercase letters and dashes
        import re
        if not re.match(r"^[a-z]+(?:-[a-z]+)*$", v):
            raise ValueError(
                "The id of the app should contain only alphabets ('a' to 'z') and dashes ('-').",
            )

        return v
