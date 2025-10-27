"""
GitHub validation utilities.

This module provides functionality to validate GitHub pull requests
and other GitHub-related resources.
"""

from __future__ import annotations

import re
from typing import Any
import httpx
from urllib.parse import urlparse

from ..core.models import LintingError, Severity


class GitHubValidator:
    """Validator for GitHub resources."""
    
    def __init__(self, timeout: float = 5.0):
        """Initialize the GitHub validator."""
        self.timeout = timeout
        self._cache: dict[str, bool] = {}
    
    async def validate_pull_request(self, pr_url: str, app_id: str) -> list[LintingError]:
        """
        Validate that a GitHub pull request URL exists and is accessible.
        
        Args:
            pr_url: GitHub pull request URL
            app_id: ID of the app being validated
            
        Returns:
            List of linting errors
        """
        errors = []
        
        # Check if URL is a valid GitHub PR URL
        if not self._is_github_pr_url(pr_url):
            errors.append(LintingError(
                id="invalid_submission_field",
                severity=Severity.ERROR,
                title=f'Invalid submission URL "{pr_url}"',
                message="Submission URL must be a valid GitHub pull request URL (e.g., https://github.com/owner/repo/pull/123)",
                file=f"{app_id}/umbrel-app.yml",
                properties_path="submission",
            ))
            return errors
        
        # Check if PR exists and is accessible
        if not await self._pr_exists(pr_url):
            errors.append(LintingError(
                id="invalid_submission_field",
                severity=Severity.ERROR,
                title=f'Pull request not found "{pr_url}"',
                message="The specified pull request does not exist or is not accessible. Please check the URL and ensure the PR is public.",
                file=f"{app_id}/umbrel-app.yml",
                properties_path="submission",
            ))
        
        return errors
    
    def _is_github_pr_url(self, url: str) -> bool:
        """Check if URL is a valid GitHub pull request URL."""
        try:
            parsed = urlparse(url)
            
            # Must be GitHub domain
            if parsed.hostname not in ["github.com", "www.github.com"]:
                return False
            
            # Must be HTTPS
            if parsed.scheme != "https":
                return False
            
            # Must match GitHub PR path pattern: /owner/repo/pull/number
            path_pattern = r"^/[^/]+/[^/]+/pull/\d+/?$"
            return bool(re.match(path_pattern, parsed.path))
            
        except Exception:
            return False
    
    async def _pr_exists(self, pr_url: str) -> bool:
        """Check if a GitHub pull request exists and is accessible.

        Uses GitHub REST API if possible for reliable status; falls back to HTML.
        """
        if pr_url in self._cache:
            return self._cache[pr_url]

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "umbrel-linter/1.0",
                    "Accept": "application/vnd.github.v3+json",
                }

                owner, repo, number = self._parse_github_pr(pr_url)
                exists = True
                if owner and repo and number:
                    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code == 200:
                        exists = True
                    elif resp.status_code == 404:
                        exists = False
                    else:
                        # On rate-limit or other statuses, do not block lint; assume exists
                        exists = True
                else:
                    # Fallback to fetching the HTML PR page
                    resp = await client.get(pr_url, headers={"User-Agent": "umbrel-linter/1.0"})
                    if resp.status_code == 200:
                        exists = True
                    elif resp.status_code == 404:
                        exists = False
                    else:
                        exists = True

                self._cache[pr_url] = exists
                return exists
        except Exception:
            # On any error, do not fail lint for existence check
            self._cache[pr_url] = True
            return True

    def _parse_github_pr(self, url: str) -> tuple[str | None, str | None, str | None]:
        try:
            parsed = urlparse(url)
            parts = [p for p in parsed.path.split('/') if p]
            # Expect: owner/repo/pull/number
            if len(parts) >= 4 and parts[2] == 'pull':
                return parts[0], parts[1], parts[3]
        except Exception:
            pass
        return None, None, None
    
    async def validate_github_urls(self, manifest_data: dict[str, Any], app_id: str) -> list[LintingError]:
        """
        Validate all GitHub URLs in a manifest.
        
        Args:
            manifest_data: Parsed manifest data
            app_id: ID of the app being validated
            
        Returns:
            List of linting errors
        """
        errors = []
        
        # Check submission URL (pull request)
        submission_url = manifest_data.get("submission")
        if submission_url:
            pr_errors = await self.validate_pull_request(str(submission_url), app_id)
            errors.extend(pr_errors)
        
        # Check repo URL (if it's a GitHub URL)
        repo_url = manifest_data.get("repo")
        if repo_url and isinstance(repo_url, str) and repo_url.strip():
            repo_errors = await self._validate_github_repo_url(str(repo_url), app_id)
            errors.extend(repo_errors)
        
        return errors
    
    async def _validate_github_repo_url(self, repo_url: str, app_id: str) -> list[LintingError]:
        """Validate a GitHub repository URL."""
        errors = []
        
        # Check if it's a valid GitHub repo URL
        if not self._is_github_repo_url(repo_url):
            errors.append(LintingError(
                id="invalid_repo_url",
                severity=Severity.WARNING,
                title=f'Invalid repository URL "{repo_url}"',
                message="Repository URL should be a valid GitHub repository URL (e.g., https://github.com/owner/repo)",
                file=f"{app_id}/umbrel-app.yml",
                properties_path="repo",
            ))
            return errors
        
        # Check if repo exists
        if not await self._repo_exists(repo_url):
            errors.append(LintingError(
                id="invalid_repo_url",
                severity=Severity.WARNING,
                title=f'Repository not found "{repo_url}"',
                message="The specified repository does not exist or is not accessible. Please check the URL.",
                file=f"{app_id}/umbrel-app.yml",
                properties_path="repo",
            ))
        
        return errors
    
    def _is_github_repo_url(self, url: str) -> bool:
        """Check if URL is a valid GitHub repository URL."""
        try:
            parsed = urlparse(url)
            
            # Must be GitHub domain
            if parsed.hostname not in ["github.com", "www.github.com"]:
                return False
            
            # Must be HTTPS
            if parsed.scheme != "https":
                return False
            
            # Must match GitHub repo path pattern: /owner/repo
            path_pattern = r"^/[^/]+/[^/]+/?$"
            return bool(re.match(path_pattern, parsed.path))
            
        except Exception:
            return False
    
    async def _repo_exists(self, repo_url: str) -> bool:
        """Check if a GitHub repository exists and is accessible."""
        if repo_url in self._cache:
            return self._cache[repo_url]
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Add headers to avoid rate limiting
                headers = {
                    "User-Agent": "umbrel-linter/1.0",
                    "Accept": "application/vnd.github.v3+json",
                }
                
                response = await client.get(repo_url, headers=headers)
                
                # Repo exists if we get 200, 404 means it doesn't exist
                exists = response.status_code == 200
                self._cache[repo_url] = exists
                return exists
                
        except Exception:
            # If we can't check (network error, etc.), assume it exists to avoid false positives
            self._cache[repo_url] = True
            return True
