"""
Variable mocking utilities for Docker Compose files.

This module provides functionality to mock environment variables
in Docker Compose files for proper validation.
"""

from __future__ import annotations

import re
from typing import Any


class VariableMocker:
    """Mocks environment variables in Docker Compose files."""
    
    def __init__(self):
        """Initialize the variable mocker."""
        pass
    
    def mock_variables(self, content: str) -> str:
        """
        Mock environment variables in Docker Compose content.
        
        Args:
            content: Docker Compose YAML content
            
        Returns:
            Content with mocked variables
        """
        variables = self._extract_variables(content)
        mocked_variables = self._find_mocks(variables)
        return self._replace_variables(content, mocked_variables)
    
    def _extract_variables(self, content: str) -> list[dict[str, str]]:
        """Extract variables from content."""
        # Match both ${VAR} and $VAR patterns
        pattern = r'\$(?:([a-zA-Z0-9_\-:]+)|\{([a-zA-Z0-9_\-:]+)\})'
        matches = re.findall(pattern, content)
        
        variables = []
        for match in matches:
            variable = match[0] if match[0] else match[1]
            full_variable = f"${{{variable}}}" if "{" in content[content.find(f"${variable}"):content.find(f"${variable}") + len(f"${variable}") + 1] else f"${variable}"
            
            variables.append({
                "full_variable": full_variable,
                "variable": variable,
                "mock": ""
            })
        
        return variables
    
    def _find_mocks(self, variables: list[dict[str, str]]) -> list[dict[str, str]]:
        """Find appropriate mock values for variables."""
        for var in variables:
            variable = var["variable"]
            
            if "_IP" in variable:
                var["mock"] = "10.10.10.10"
            elif "_PORT" in variable:
                # Random port between 1024 and 65535 to make json schema happy
                import random
                var["mock"] = str(random.randint(1024, 65535))
            elif "_PASS" in variable:
                var["mock"] = "password"
            elif "_USER" in variable:
                var["mock"] = "username"
            elif "_DIR" in variable:
                var["mock"] = "/path/to/dir"
            elif "_PATH" in variable:
                var["mock"] = "/some/path"
            elif "_SERVICE" in variable:
                var["mock"] = "service"
            elif "_SEED" in variable:
                var["mock"] = "seed"
            elif "_CONFIG" in variable:
                var["mock"] = "/path/to/config"
            elif "_MODE" in variable:
                var["mock"] = "production"
            elif "_NETWORK" in variable:
                var["mock"] = "network"
            elif "_DOMAIN" in variable:
                var["mock"] = "domain.com"
            elif "_NAME" in variable:
                var["mock"] = "name"
            elif "_VERSION" in variable:
                var["mock"] = "1.0.0"
            elif "_ROOT" in variable:
                var["mock"] = "/path/to/root"
            elif "_KEY" in variable:
                var["mock"] = "key"
            elif "_SECRET" in variable:
                var["mock"] = "secret"
            elif "_TOKEN" in variable:
                var["mock"] = "token"
            elif "_HOST" in variable:
                var["mock"] = "host"
            else:
                var["mock"] = "mocked"
        
        return variables
    
    def _replace_variables(self, content: str, variables: list[dict[str, str]]) -> str:
        """Replace variables with their mock values."""
        for var in variables:
            content = content.replace(var["full_variable"], var["mock"])
        return content
