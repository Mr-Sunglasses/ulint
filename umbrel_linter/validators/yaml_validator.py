"""
YAML validation utilities.

This module provides functions for validating YAML files and extracting
source map information for error reporting.
"""

from __future__ import annotations

from typing import Any

import yaml

from ..core.models import ColumnRange, LineRange, LintingError, Severity


def parse_yaml_with_error_handling(content: str, filename: str) -> tuple[dict[str, Any] | None, LintingError | None]:
    """
    Parse YAML content with comprehensive error handling.
    
    Args:
        content: YAML content as string
        filename: Name of the file being parsed
        
    Returns:
        Tuple of (parsed_data, error). If parsing succeeds, error is None.
        If parsing fails, parsed_data is None and error contains details.
    """
    try:
        data = yaml.safe_load(content)
        return data, None
    except yaml.YAMLError as e:
        error = LintingError(
            id="invalid_yaml_syntax",
            severity=Severity.ERROR,
            title=f"{filename} is not a valid YAML file",
            message=str(e),
            file=filename,
        )
        return None, error


def get_source_map_for_path(content: str, path: list[str]) -> dict[str, LineRange | ColumnRange]:
    """
    Extract source map information for a given JSON path.
    
    This is a simplified implementation. In a real implementation, you would
    use a proper YAML parser with source map support like ruamel.yaml.
    
    Args:
        content: YAML content as string
        path: JSON path to the property
        
    Returns:
        Dictionary with line and column information
    """
    lines = content.split("\n")
    result = {}

    # Simple line-based search for the property
    for i, line in enumerate(lines):
        if any(part in line for part in path):
            result["line"] = LineRange(start=i + 1, end=i + 1)
            # Find column position (simplified)
            for j, char in enumerate(line):
                if char in [":", "="]:
                    result["column"] = ColumnRange(start=j + 1, end=j + 1)
                    break
            break

    return result


def validate_yaml_structure(data: dict[str, Any], required_fields: list[str], filename: str) -> list[LintingError]:
    """
    Validate that required fields exist in the YAML data.
    
    Args:
        data: Parsed YAML data
        required_fields: List of required field names
        filename: Name of the file being validated
        
    Returns:
        List of linting errors for missing fields
    """
    errors = []

    for field in required_fields:
        if field not in data:
            errors.append(LintingError(
                id="missing_required_field",
                severity=Severity.ERROR,
                title=f"Missing required field: {field}",
                message=f"The '{field}' field is required in {filename}",
                file=filename,
                properties_path=field,
            ))

    return errors


def validate_yaml_types(data: dict[str, Any], type_mapping: dict[str, type], filename: str) -> list[LintingError]:
    """
    Validate that fields have the correct types.
    
    Args:
        data: Parsed YAML data
        type_mapping: Dictionary mapping field names to expected types
        filename: Name of the file being validated
        
    Returns:
        List of linting errors for type mismatches
    """
    errors = []

    for field, expected_type in type_mapping.items():
        if field in data:
            value = data[field]
            if not isinstance(value, expected_type):
                errors.append(LintingError(
                    id="invalid_type",
                    severity=Severity.ERROR,
                    title=f"Invalid type for field: {field}",
                    message=f"Expected {expected_type.__name__}, got {type(value).__name__}",
                    file=filename,
                    properties_path=field,
                ))

    return errors


def validate_boolean_strings(data: dict[str, Any], filename: str) -> list[LintingError]:
    """
    Validate that boolean values are strings (for Docker Compose V1 compatibility).
    
    Args:
        data: Parsed YAML data
        filename: Name of the file being validated
        
    Returns:
        List of linting errors for boolean type issues
    """
    errors = []

    def check_dict(d: dict[str, Any], path: str = "") -> None:
        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, dict):
                check_dict(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        check_dict(item, f"{current_path}[{i}]")
            elif isinstance(value, bool):
                errors.append(LintingError(
                    id="invalid_yaml_boolean_value",
                    severity=Severity.ERROR,
                    title=f"Invalid YAML boolean value for key '{key}'",
                    message=f"Boolean values should be strings like '{str(value).lower()}' instead of {value}",
                    file=filename,
                    properties_path=current_path,
                ))

    check_dict(data)
    return errors
