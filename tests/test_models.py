"""
Tests for core models.

This module contains tests for the core data models used throughout the linter.
"""

import pytest
from pydantic import ValidationError

from umbrel_linter.core.models import (
    LintingError, 
    Severity, 
    LineRange, 
    ColumnRange,
    LintingResult,
    FileEntry,
    LinterConfig,
    LintingContext,
    AppStoreType
)


class TestLintingError:
    """Test LintingError model."""
    
    def test_create_linting_error(self):
        """Test creating a linting error."""
        error = LintingError(
            id="test_error",
            severity=Severity.ERROR,
            title="Test Error",
            message="This is a test error",
            file="test.yml"
        )
        
        assert error.id == "test_error"
        assert error.severity == Severity.ERROR
        assert error.title == "Test Error"
        assert error.message == "This is a test error"
        assert error.file == "test.yml"
        assert error.properties_path is None
        assert error.line is None
        assert error.column is None
    
    def test_create_linting_error_with_optional_fields(self):
        """Test creating a linting error with optional fields."""
        line_range = LineRange(start=1, end=5)
        column_range = ColumnRange(start=10, end=20)
        
        error = LintingError(
            id="test_error",
            severity=Severity.WARNING,
            title="Test Warning",
            message="This is a test warning",
            file="test.yml",
            properties_path="services.app",
            line=line_range,
            column=column_range
        )
        
        assert error.properties_path == "services.app"
        assert error.line == line_range
        assert error.column == column_range


class TestLineRange:
    """Test LineRange model."""
    
    def test_create_line_range(self):
        """Test creating a line range."""
        line_range = LineRange(start=1, end=5)
        assert line_range.start == 1
        assert line_range.end == 5
    
    def test_line_range_validation(self):
        """Test line range validation."""
        # Valid range
        line_range = LineRange(start=1, end=5)
        assert line_range.start == 1
        assert line_range.end == 5
        
        # Same start and end
        line_range = LineRange(start=3, end=3)
        assert line_range.start == 3
        assert line_range.end == 3
    
    def test_line_range_invalid_end(self):
        """Test line range with invalid end."""
        with pytest.raises(ValidationError):
            LineRange(start=5, end=1)  # end < start


class TestColumnRange:
    """Test ColumnRange model."""
    
    def test_create_column_range(self):
        """Test creating a column range."""
        column_range = ColumnRange(start=10, end=20)
        assert column_range.start == 10
        assert column_range.end == 20
    
    def test_column_range_validation(self):
        """Test column range validation."""
        # Valid range
        column_range = ColumnRange(start=10, end=20)
        assert column_range.start == 10
        assert column_range.end == 20
        
        # Same start and end
        column_range = ColumnRange(start=15, end=15)
        assert column_range.start == 15
        assert column_range.end == 15
    
    def test_column_range_invalid_end(self):
        """Test column range with invalid end."""
        with pytest.raises(ValidationError):
            ColumnRange(start=20, end=10)  # end < start


class TestLintingResult:
    """Test LintingResult model."""
    
    def test_create_empty_result(self):
        """Test creating an empty result."""
        result = LintingResult()
        assert result.errors == []
        assert result.success is True
        assert result.total_errors == 0
        assert result.total_warnings == 0
        assert result.total_info == 0
    
    def test_add_error(self):
        """Test adding an error to result."""
        result = LintingResult()
        error = LintingError(
            id="test_error",
            severity=Severity.ERROR,
            title="Test Error",
            message="This is a test error",
            file="test.yml"
        )
        
        result.add_error(error)
        
        assert len(result.errors) == 1
        assert result.errors[0] == error
        assert result.success is False
        assert result.total_errors == 1
        assert result.total_warnings == 0
        assert result.total_info == 0
    
    def test_add_warning(self):
        """Test adding a warning to result."""
        result = LintingResult()
        warning = LintingError(
            id="test_warning",
            severity=Severity.WARNING,
            title="Test Warning",
            message="This is a test warning",
            file="test.yml"
        )
        
        result.add_error(warning)
        
        assert len(result.errors) == 1
        assert result.success is False
        assert result.total_errors == 0
        assert result.total_warnings == 1
        assert result.total_info == 0
    
    def test_add_info(self):
        """Test adding an info message to result."""
        result = LintingResult()
        info = LintingError(
            id="test_info",
            severity=Severity.INFO,
            title="Test Info",
            message="This is a test info message",
            file="test.yml"
        )
        
        result.add_error(info)
        
        assert len(result.errors) == 1
        assert result.success is False
        assert result.total_errors == 0
        assert result.total_warnings == 0
        assert result.total_info == 1
    
    def test_has_errors(self):
        """Test has_errors method."""
        result = LintingResult()
        assert not result.has_errors()
        
        # Add warning - should not count as error
        warning = LintingError(
            id="test_warning",
            severity=Severity.WARNING,
            title="Test Warning",
            message="This is a test warning",
            file="test.yml"
        )
        result.add_error(warning)
        assert not result.has_errors()
        
        # Add error - should count as error
        error = LintingError(
            id="test_error",
            severity=Severity.ERROR,
            title="Test Error",
            message="This is a test error",
            file="test.yml"
        )
        result.add_error(error)
        assert result.has_errors()
    
    def test_has_warnings(self):
        """Test has_warnings method."""
        result = LintingResult()
        assert not result.has_warnings()
        
        # Add info - should not count as warning
        info = LintingError(
            id="test_info",
            severity=Severity.INFO,
            title="Test Info",
            message="This is a test info message",
            file="test.yml"
        )
        result.add_error(info)
        assert not result.has_warnings()
        
        # Add warning - should count as warning
        warning = LintingError(
            id="test_warning",
            severity=Severity.WARNING,
            title="Test Warning",
            message="This is a test warning",
            file="test.yml"
        )
        result.add_error(warning)
        assert result.has_warnings()
    
    def test_has_info(self):
        """Test has_info method."""
        result = LintingResult()
        assert not result.has_info()
        
        # Add error - should not count as info
        error = LintingError(
            id="test_error",
            severity=Severity.ERROR,
            title="Test Error",
            message="This is a test error",
            file="test.yml"
        )
        result.add_error(error)
        assert not result.has_info()
        
        # Add info - should count as info
        info = LintingError(
            id="test_info",
            severity=Severity.INFO,
            title="Test Info",
            message="This is a test info message",
            file="test.yml"
        )
        result.add_error(info)
        assert result.has_info()


class TestFileEntry:
    """Test FileEntry model."""
    
    def test_create_file_entry(self):
        """Test creating a file entry."""
        entry = FileEntry(path="test.yml", type="file")
        assert entry.path == "test.yml"
        assert entry.type == "file"
    
    def test_create_directory_entry(self):
        """Test creating a directory entry."""
        entry = FileEntry(path="test_dir", type="directory")
        assert entry.path == "test_dir"
        assert entry.type == "directory"
    
    def test_invalid_type(self):
        """Test invalid type validation."""
        with pytest.raises(ValidationError):
            FileEntry(path="test.yml", type="invalid")


class TestLinterConfig:
    """Test LinterConfig model."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = LinterConfig()
        assert config.check_image_architectures is False
        assert config.log_level == Severity.WARNING
        assert config.strict_mode is False
        assert config.ignore_patterns == []
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LinterConfig(
            check_image_architectures=True,
            log_level=Severity.ERROR,
            strict_mode=True,
            ignore_patterns=["*.tmp", "*.log"]
        )
        assert config.check_image_architectures is True
        assert config.log_level == Severity.ERROR
        assert config.strict_mode is True
        assert config.ignore_patterns == ["*.tmp", "*.log"]


class TestLintingContext:
    """Test LintingContext model."""
    
    def test_default_context(self):
        """Test default context."""
        context = LintingContext()
        assert context.app_id is None
        assert context.app_store_type == AppStoreType.COMMUNITY
        assert context.is_new_submission is False
        assert context.pull_request_url is None
        assert context.all_app_manifests == []
    
    def test_custom_context(self):
        """Test custom context."""
        context = LintingContext(
            app_id="test-app",
            app_store_type=AppStoreType.OFFICIAL,
            is_new_submission=True,
            pull_request_url="https://github.com/user/repo/pull/123",
            all_app_manifests=["manifest1", "manifest2"]
        )
        assert context.app_id == "test-app"
        assert context.app_store_type == AppStoreType.OFFICIAL
        assert context.is_new_submission is True
        assert context.pull_request_url == "https://github.com/user/repo/pull/123"
        assert context.all_app_manifests == ["manifest1", "manifest2"]
