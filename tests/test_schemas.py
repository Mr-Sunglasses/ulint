"""
Tests for schema validation.

This module contains tests for the Pydantic schemas used for validation.
"""

import pytest
from pydantic import ValidationError

from umbrel_linter.schemas.umbrel_app import UmbrelAppManifest, UmbrelAppStoreManifest


class TestUmbrelAppManifest:
    """Test UmbrelAppManifest schema."""
    
    def test_valid_manifest(self):
        """Test valid manifest creation."""
        manifest_data = {
            "manifest_version": 1,
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application",
            "category": "files",
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app"
        }
        
        manifest = UmbrelAppManifest(**manifest_data)
        assert manifest.id == "test-app"
        assert manifest.name == "Test App"
        assert manifest.port == 3000
    
    def test_invalid_manifest_version(self):
        """Test invalid manifest version."""
        manifest_data = {
            "manifest_version": 2.0,  # Invalid version
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application",
            "category": "files",
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppManifest(**manifest_data)
        
        assert "manifest_version" in str(exc_info.value)
    
    def test_invalid_app_id(self):
        """Test invalid app ID."""
        manifest_data = {
            "manifest_version": 1,
            "id": "umbrel-app-store-test",  # Invalid ID
            "name": "Test App",
            "tagline": "A test application",
            "category": "files",
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppManifest(**manifest_data)
        
        assert "umbrel-app-store" in str(exc_info.value)
    
    def test_invalid_tagline(self):
        """Test invalid tagline."""
        manifest_data = {
            "manifest_version": 1,
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application.",  # Ends with period
            "category": "files",
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppManifest(**manifest_data)
        
        assert "period" in str(exc_info.value)
    
    def test_invalid_category(self):
        """Test invalid category."""
        manifest_data = {
            "manifest_version": 1,
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application",
            "category": "invalid_category",  # Invalid category
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppManifest(**manifest_data)
        
        assert "category" in str(exc_info.value)
    
    def test_invalid_port(self):
        """Test invalid port."""
        manifest_data = {
            "manifest_version": 1,
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application",
            "category": "files",
            "version": "1.0.0",
            "port": 70000,  # Invalid port
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppManifest(**manifest_data)
        
        assert "port" in str(exc_info.value)
    
    def test_self_dependency(self):
        """Test self-dependency validation."""
        manifest_data = {
            "manifest_version": 1,
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application",
            "category": "files",
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app",
            "dependencies": ["test-app"]  # Self-dependency
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppManifest(**manifest_data)
        
        assert "Dependencies" in str(exc_info.value)
    
    def test_optional_fields(self):
        """Test optional fields."""
        manifest_data = {
            "manifest_version": 1,
            "id": "test-app",
            "name": "Test App",
            "tagline": "A test application",
            "category": "files",
            "version": "1.0.0",
            "port": 3000,
            "description": "This is a test application",
            "developer": "Test Developer",
            "submitter": "Test Submitter",
            "submission": "https://github.com/user/repo/pull/123",
            "support": "https://example.com/support",
            "website": "https://example.com",
            "path": "/app",
            "icon": "https://example.com/icon.png",
            "gallery": ["https://example.com/image1.png"],
            "release_notes": "Version 1.0.0",
            "dependencies": ["other-app"],
            "permissions": ["STORAGE_DOWNLOADS"],
            "default_username": "admin",
            "default_password": "password",
            "deterministic_password": True,
            "optimized_for_umbrel_home": True,
            "tor_only": False,
            "install_size": 1024,
            "default_shell": "/bin/bash",
            "backup_ignore": ["*.log", "*.tmp"],
            "repo": "https://github.com/user/repo"
        }
        
        manifest = UmbrelAppManifest(**manifest_data)
        assert manifest.icon == "https://example.com/icon.png"
        assert manifest.gallery == ["https://example.com/image1.png"]
        assert manifest.release_notes == "Version 1.0.0"
        assert manifest.dependencies == ["other-app"]
        assert manifest.permissions == ["STORAGE_DOWNLOADS"]
        assert manifest.default_username == "admin"
        assert manifest.default_password == "password"
        assert manifest.deterministic_password is True
        assert manifest.optimized_for_umbrel_home is True
        assert manifest.tor_only is False
        assert manifest.install_size == 1024
        assert manifest.default_shell == "/bin/bash"
        assert manifest.backup_ignore == ["*.log", "*.tmp"]
        assert manifest.repo == "https://github.com/user/repo"


class TestUmbrelAppStoreManifest:
    """Test UmbrelAppStoreManifest schema."""
    
    def test_valid_store_manifest(self):
        """Test valid store manifest creation."""
        store_data = {
            "id": "my-app-store",
            "name": "My App Store"
        }
        
        store = UmbrelAppStoreManifest(**store_data)
        assert store.id == "my-app-store"
        assert store.name == "My App Store"
    
    def test_invalid_store_id_reserved(self):
        """Test invalid store ID with reserved prefix."""
        store_data = {
            "id": "umbrel-app-store-test",  # Reserved prefix
            "name": "Test Store"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppStoreManifest(**store_data)
        
        assert "umbrel-app-store" in str(exc_info.value)
    
    def test_invalid_store_id_format(self):
        """Test invalid store ID format."""
        store_data = {
            "id": "My_App_Store",  # Invalid format (uppercase, underscores)
            "name": "Test Store"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UmbrelAppStoreManifest(**store_data)
        
        assert "alphabets" in str(exc_info.value)
    
    def test_valid_store_id_with_dashes(self):
        """Test valid store ID with dashes."""
        store_data = {
            "id": "my-awesome-app-store",
            "name": "My Awesome App Store"
        }
        
        store = UmbrelAppStoreManifest(**store_data)
        assert store.id == "my-awesome-app-store"
        assert store.name == "My Awesome App Store"
