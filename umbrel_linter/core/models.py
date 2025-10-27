"""
Core data models for the Umbrel linter.

This module defines the fundamental data structures used throughout the linter,
including linting results, error types, and configuration models.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, validator


class Severity(str, Enum):
    """Severity levels for linting results."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LintingError(BaseModel):
    """Represents a linting error with detailed information."""

    id: str = Field(..., description="Unique identifier for the error type")
    severity: Severity = Field(..., description="Severity level of the error")
    title: str = Field(..., description="Short title describing the error")
    message: str = Field(..., description="Detailed error message")
    file: str = Field(..., description="File path where the error occurred")
    properties_path: str | None = Field(None, description="JSON path to the problematic property")
    line: LineRange | None = Field(None, description="Line range where the error occurred")
    column: ColumnRange | None = Field(None, description="Column range where the error occurred")

    class Config:
        """Pydantic configuration."""
        pass


class LineRange(BaseModel):
    """Represents a range of lines in a file."""

    start: int = Field(..., ge=1, description="Starting line number (1-indexed)")
    end: int = Field(..., ge=1, description="Ending line number (1-indexed)")

    @validator("end")
    def end_must_be_gte_start(cls, v, values):
        """Ensure end line is greater than or equal to start line."""
        if "start" in values and v < values["start"]:
            raise ValueError("end must be greater than or equal to start")
        return v


class ColumnRange(BaseModel):
    """Represents a range of columns in a file."""

    start: int = Field(..., ge=1, description="Starting column number (1-indexed)")
    end: int = Field(..., ge=1, description="Ending column number (1-indexed)")

    @validator("end")
    def end_must_be_gte_start(cls, v, values):
        """Ensure end column is greater than or equal to start column."""
        if "start" in values and v < values["start"]:
            raise ValueError("end must be greater than or equal to start")
        return v


class LintingResult(BaseModel):
    """Container for linting results."""

    errors: list[LintingError] = Field(default_factory=list, description="List of linting errors")
    success: bool = Field(True, description="Whether linting was successful")
    total_errors: int = Field(0, description="Total number of errors")
    total_warnings: int = Field(0, description="Total number of warnings")
    total_info: int = Field(0, description="Total number of info messages")

    def add_error(self, error: LintingError) -> None:
        """Add a linting error to the result."""
        self.errors.append(error)
        
        # Only set success to False for actual errors (not info messages)
        if error.severity == Severity.ERROR:
            self.success = False

        # Update counters
        if error.severity == Severity.ERROR:
            self.total_errors += 1
        elif error.severity == Severity.WARNING:
            self.total_warnings += 1
        elif error.severity == Severity.INFO:
            self.total_info += 1

    def has_errors(self) -> bool:
        """Check if there are any errors (not just warnings or info)."""
        return any(error.severity == Severity.ERROR for error in self.errors)

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(error.severity == Severity.WARNING for error in self.errors)

    def has_info(self) -> bool:
        """Check if there are any info messages."""
        return any(error.severity == Severity.INFO for error in self.errors)


class FileEntry(BaseModel):
    """Represents a file or directory entry."""

    path: str = Field(..., description="Path to the file or directory")
    type: str = Field(..., description="Type: 'file' or 'directory'")

    @validator("type")
    def type_must_be_valid(cls, v):
        """Ensure type is either 'file' or 'directory'."""
        if v not in ["file", "directory"]:
            raise ValueError('type must be either "file" or "directory"')
        return v


class LinterConfig(BaseModel):
    """Configuration for the linter."""

    check_image_architectures: bool = Field(
        default=True,
        description="Whether to check Docker image architectures",
    )
    log_level: Severity = Field(
        default=Severity.WARNING,
        description="Minimum log level to display",
    )
    strict_mode: bool = Field(
        default=False,
        description="Whether to run in strict mode (treat warnings as errors)",
    )
    ignore_patterns: list[str] = Field(
        default_factory=list,
        description="File patterns to ignore during linting",
    )

    class Config:
        """Pydantic configuration."""
        pass


class AppStoreType(str, Enum):
    """Type of app store."""

    OFFICIAL = "official"
    COMMUNITY = "community"


class LintingContext(BaseModel):
    """Context information for linting operations."""

    app_id: str | None = Field(None, description="ID of the app being linted")
    app_store_type: AppStoreType = Field(
        default=AppStoreType.COMMUNITY,
        description="Type of app store",
    )
    is_new_submission: bool = Field(
        default=False,
        description="Whether this is a new app submission",
    )
    pull_request_url: str | None = Field(
        None,
        description="URL of the pull request for new submissions",
    )
    all_app_manifests: list[str] = Field(
        default_factory=list,
        description="All app manifest contents for cross-validation",
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
