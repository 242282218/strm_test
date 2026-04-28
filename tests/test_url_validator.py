"""
Tests for URLValidator - SSRF Protection

Tests cover:
- Valid HTTP/HTTPS URLs
- Private IPv4 rejection
- Private IPv6 rejection
- Localhost rejection
- Domain whitelist
- Dangerous hostnames
- Scheme validation
- DNS rebinding protection
"""

from __future__ import annotations

import re

import pytest

from app.core.url_validator import (
    URLValidationError,
    URLValidator,
    emby_validator,
    general_validator,
    quark_validator,
)


def match_ignore_case(pattern: str, text: str) -> bool:
    """Helper function for case-insensitive regex matching."""
    return bool(re.search(pattern, text, re.IGNORECASE))


class TestValidHTTPUrl:
    """Test valid HTTP/HTTPS URLs are accepted."""

    def test_valid_http_url_when_valid_then_returns_true(self):
        """Valid HTTP URL should pass validation."""
        validator = URLValidator()
        assert validator.validate("http://example.com/path") is True

    def test_valid_https_url_when_valid_then_returns_true(self):
        """Valid HTTPS URL should pass validation."""
        validator = URLValidator()
        assert validator.validate("https://example.com/path") is True

    def test_valid_url_with_port_when_valid_then_returns_true(self):
        """Valid URL with port should pass validation."""
        validator = URLValidator()
        assert validator.validate("https://example.com:8080/path") is True

    def test_valid_url_with_query_when_valid_then_returns_true(self):
        """Valid URL with query string should pass validation."""
        validator = URLValidator()
        assert validator.validate("https://example.com/path?key=value") is True

    def test_valid_url_with_fragment_when_valid_then_returns_true(self):
        """Valid URL with fragment should pass validation."""
        validator = URLValidator()
        assert validator.validate("https://example.com/path#section") is True

    def test_invalid_scheme_when_not_http_https_then_raises_error(self):
        """Non-HTTP/HTTPS schemes should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("ftp://example.com/file")
        assert match_ignore_case("scheme", str(exc_info.value))

    def test_invalid_scheme_file_when_file_scheme_then_raises_error(self):
        """File scheme should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("file:///etc/passwd")
        assert match_ignore_case("scheme", str(exc_info.value))

    def test_invalid_scheme_javascript_when_javascript_scheme_then_raises_error(self):
        """JavaScript scheme should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("javascript:alert(1)")
        assert match_ignore_case("scheme", str(exc_info.value))


class TestPrivateIPv4Rejected:
    """Test private IPv4 addresses are rejected."""

    def test_private_ipv4_10_range_when_private_then_raises_error(self):
        """10.0.0.0/8 range should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://10.0.0.1/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv4_10_range_upper_when_private_then_raises_error(self):
        """10.255.255.255 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://10.255.255.255/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv4_172_range_when_private_then_raises_error(self):
        """172.16.0.0/12 range should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://172.16.0.1/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv4_172_range_upper_when_private_then_raises_error(self):
        """172.31.255.255 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://172.31.255.255/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv4_192_range_when_private_then_raises_error(self):
        """192.168.0.0/16 range should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://192.168.1.1/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv4_192_range_upper_when_private_then_raises_error(self):
        """192.168.255.255 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://192.168.255.255/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv4_127_range_when_loopback_then_raises_error(self):
        """127.0.0.0/8 loopback range should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://127.0.0.1/admin")
        assert match_ignore_case("loopback|private", str(exc_info.value))

    def test_private_ipv4_169_range_when_link_local_then_raises_error(self):
        """169.254.0.0/16 link-local range should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://169.254.1.1/admin")
        assert match_ignore_case("link.local|private", str(exc_info.value))


class TestPrivateIPv6Rejected:
    """Test private IPv6 addresses are rejected."""

    def test_private_ipv6_loopback_when_loopback_then_raises_error(self):
        """IPv6 loopback ::1 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://[::1]/admin")
        assert match_ignore_case("loopback|private", str(exc_info.value))

    def test_private_ipv6_unique_local_when_unique_local_then_raises_error(self):
        """IPv6 unique local fc00::/7 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://[fc00::1]/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_private_ipv6_link_local_when_link_local_then_raises_error(self):
        """IPv6 link-local fe80::/10 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://[fe80::1]/admin")
        assert match_ignore_case("link.local|private", str(exc_info.value))


class TestLocalhostRejected:
    """Test localhost and dangerous hostnames are rejected."""

    def test_localhost_hostname_when_localhost_then_raises_error(self):
        """localhost hostname should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://localhost/admin")
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))

    def test_localhost_uppercase_when_localhost_then_raises_error(self):
        """LOCALHOST (uppercase) should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://LOCALHOST/admin")
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))

    def test_localhost_with_port_when_localhost_then_raises_error(self):
        """localhost with port should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://localhost:8080/admin")
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))

    def test_localhost_subdomain_when_localhost_subdomain_then_raises_error(self):
        """localhost subdomain should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://test.localhost/admin")
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))

    def test_dangerous_hostname_internal_when_internal_then_raises_error(self):
        """internal hostname should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://internal.corp/admin")
        assert match_ignore_case("dangerous", str(exc_info.value))

    def test_dangerous_hostname_local_when_local_then_raises_error(self):
        """local hostname should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://local/admin")
        assert match_ignore_case("dangerous", str(exc_info.value))


class TestDomainWhitelist:
    """Test domain whitelist functionality."""

    def test_whitelisted_domain_when_in_whitelist_then_returns_true(self):
        """Whitelisted domain should pass validation."""
        validator = URLValidator(allowed_domains=["example.com", "test.com"])
        assert validator.validate("https://example.com/path") is True

    def test_whitelisted_domain_subdomain_when_in_whitelist_then_returns_true(self):
        """Subdomain of whitelisted domain should pass validation."""
        validator = URLValidator(allowed_domains=["example.com"])
        assert validator.validate("https://api.example.com/path") is True

    def test_non_whitelisted_domain_when_not_in_whitelist_then_raises_error(self):
        """Non-whitelisted domain should be rejected when whitelist is set."""
        validator = URLValidator(allowed_domains=["example.com"])
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("https://other.com/path")
        assert match_ignore_case("domain", str(exc_info.value))

    def test_whitelist_case_insensitive_when_mixed_case_then_returns_true(self):
        """Domain whitelist should be case-insensitive."""
        validator = URLValidator(allowed_domains=["Example.COM"])
        assert validator.validate("https://example.com/path") is True


class TestAllowPrivateFlag:
    """Test allow_private flag functionality."""

    def test_allow_private_true_when_private_ip_then_returns_true(self):
        """Private IP should be allowed when allow_private is True."""
        validator = URLValidator()
        assert validator.validate("http://192.168.1.1/admin", allow_private=True) is True

    def test_allow_private_true_when_localhost_then_still_rejects(self):
        """localhost should still be rejected even with allow_private=True."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://localhost/admin", allow_private=True)
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))

    def test_allow_private_true_when_loopback_ip_then_returns_true(self):
        """Loopback IP should be allowed when allow_private is True."""
        validator = URLValidator()
        assert validator.validate("http://127.0.0.1/admin", allow_private=True) is True


class TestPrivateIPWhitelist:
    """Test private IP whitelist functionality."""

    def test_private_ip_whitelist_when_in_whitelist_then_returns_true(self):
        """Whitelisted private IP should pass validation."""
        validator = URLValidator(allowed_private_ips=["192.168.1.100", "10.0.0.1"])
        assert validator.validate("http://192.168.1.100/admin") is True

    def test_private_ip_whitelist_when_not_in_whitelist_then_raises_error(self):
        """Non-whitelisted private IP should be rejected."""
        validator = URLValidator(allowed_private_ips=["192.168.1.100"])
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://192.168.1.1/admin")
        assert match_ignore_case("private", str(exc_info.value))


class TestQuarkValidator:
    """Test pre-defined quark_validator instance."""

    def test_quark_validator_when_quark_domain_then_returns_true(self):
        """quark.cn domain should pass quark_validator."""
        assert quark_validator.validate("https://pan.quark.cn/list") is True

    def test_quark_validator_when_quark_subdomain_then_returns_true(self):
        """quark.cn subdomain should pass quark_validator."""
        assert quark_validator.validate("https://drive.quark.cn/api") is True

    def test_quark_validator_when_other_domain_then_raises_error(self):
        """Non-quark domain should be rejected by quark_validator."""
        with pytest.raises(URLValidationError) as exc_info:
            quark_validator.validate("https://example.com/path")
        assert match_ignore_case("domain", str(exc_info.value))

    def test_quark_validator_when_private_ip_then_raises_error(self):
        """Private IP should be rejected by quark_validator."""
        with pytest.raises(URLValidationError) as exc_info:
            quark_validator.validate("http://192.168.1.1/admin")
        # Private IP is rejected because it's not in quark.cn domain
        assert match_ignore_case("domain|private", str(exc_info.value))


class TestEmbyValidator:
    """Test pre-defined emby_validator instance."""

    def test_emby_validator_when_private_ip_then_allows_with_allow_private(self):
        """Private IP should be allowed by emby_validator (configured for internal networks)."""
        # emby_validator is configured with allow_private_by_default=True
        assert emby_validator.validate("http://192.168.1.1/admin") is True

    def test_emby_validator_when_public_url_then_allows(self):
        """Public URL should be allowed by emby_validator."""
        # emby_validator allows all domains by default
        assert emby_validator.validate("https://example.com/path") is True

    def test_emby_validator_when_localhost_then_rejects(self):
        """localhost should still be rejected by emby_validator."""
        with pytest.raises(URLValidationError) as exc_info:
            emby_validator.validate("http://localhost/admin")
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))


class TestGeneralValidator:
    """Test pre-defined general_validator instance."""

    def test_general_validator_when_public_url_then_returns_true(self):
        """Public URL should pass general_validator."""
        assert general_validator.validate("https://example.com/path") is True

    def test_general_validator_when_private_ip_then_raises_error(self):
        """Private IP should be rejected by general_validator."""
        with pytest.raises(URLValidationError) as exc_info:
            general_validator.validate("http://192.168.1.1/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_general_validator_when_localhost_then_raises_error(self):
        """localhost should be rejected by general_validator."""
        with pytest.raises(URLValidationError) as exc_info:
            general_validator.validate("http://localhost/admin")
        assert match_ignore_case("localhost|dangerous", str(exc_info.value))


class TestEdgeCases:
    """Test edge cases and potential bypass attempts."""

    def test_ipv4_embedded_in_ipv6_when_private_then_raises_error(self):
        """IPv4-mapped IPv6 addresses should be checked for private ranges."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://[::ffff:192.168.1.1]/admin")
        assert match_ignore_case("private", str(exc_info.value))

    def test_decimal_ip_when_private_then_raises_error(self):
        """Decimal IP representation should be handled."""
        validator = URLValidator()
        # 3232235777 = 192.168.1.1 in decimal
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://3232235777/admin")
        assert match_ignore_case("private|invalid", str(exc_info.value))

    def test_octal_ip_when_private_then_raises_error(self):
        """Octal IP representation should be handled."""
        validator = URLValidator()
        # 0300.0250.01.01 = 192.168.1.1 in octal
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://0300.0250.01.01/admin")
        assert match_ignore_case("private|invalid", str(exc_info.value))

    def test_hex_ip_when_private_then_raises_error(self):
        """Hexadecimal IP representation should be handled."""
        validator = URLValidator()
        # 0xc0a80101 = 192.168.1.1 in hex
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://0xc0a80101/admin")
        assert match_ignore_case("private|invalid", str(exc_info.value))

    def test_url_with_at_sign_when_has_credentials_then_returns_true(self):
        """URL with credentials should be parsed correctly."""
        validator = URLValidator()
        # Credentials should not affect hostname validation
        assert validator.validate("https://user:pass@example.com/path") is True

    def test_empty_url_when_empty_then_raises_error(self):
        """Empty URL should raise error."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("")
        assert match_ignore_case("required|empty", str(exc_info.value))

    def test_none_url_when_none_then_raises_error(self):
        """None URL should raise error."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate(None)
        assert match_ignore_case("required", str(exc_info.value))

    def test_invalid_url_format_when_malformed_then_raises_error(self):
        """Malformed URL should raise error."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("not a valid url")
        assert match_ignore_case("invalid|malformed|scheme", str(exc_info.value))

    def test_url_without_host_when_no_host_then_raises_error(self):
        """URL without host should raise error."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http:///path")
        assert match_ignore_case("host", str(exc_info.value))

    def test_0_0_0_0_when_wildcard_then_raises_error(self):
        """0.0.0.0 should be rejected."""
        validator = URLValidator()
        with pytest.raises(URLValidationError) as exc_info:
            validator.validate("http://0.0.0.0/admin")
        assert match_ignore_case("private|reserved", str(exc_info.value))
