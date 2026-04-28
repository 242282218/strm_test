"""
URL Validator - SSRF Protection

Provides comprehensive URL validation to prevent Server-Side Request Forgery (SSRF) attacks.
Validates URLs against:
- Allowed schemes (HTTP/HTTPS only)
- Private IP ranges (RFC 1918, RFC 4193)
- Dangerous hostnames (localhost, internal, etc.)
- Domain whitelists
- Private IP whitelists

Reference:
- RFC 1918: Private IPv4 addresses
- RFC 4193: Unique local IPv6 addresses
- OWASP SSRF Prevention Cheat Sheet
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


class URLValidationError(ValueError):
    """URL validation error for SSRF protection."""


class URLValidator:
    """
    URL validator for SSRF protection.

    Validates URLs to prevent access to internal resources and private networks.
    Supports domain whitelists, private IP whitelists, and configurable policies.
    """

    # Allowed URL schemes
    ALLOWED_SCHEMES: set[str] = {"http", "https"}

    # RFC 1918 Private IPv4 ranges
    PRIVATE_IPV4_RANGES: list[ipaddress.IPv4Network] = [
        ipaddress.IPv4Network("10.0.0.0/8"),  # Class A private
        ipaddress.IPv4Network("172.16.0.0/12"),  # Class B private
        ipaddress.IPv4Network("192.168.0.0/16"),  # Class C private
        ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
        ipaddress.IPv4Network("169.254.0.0/16"),  # Link-local
        ipaddress.IPv4Network("0.0.0.0/8"),  # "This network" (includes 0.0.0.0)
    ]

    # RFC 4193 Private IPv6 ranges
    PRIVATE_IPV6_RANGES: list[ipaddress.IPv6Network] = [
        ipaddress.IPv6Network("::1/128"),  # Loopback
        ipaddress.IPv6Network("fc00::/7"),  # Unique local
        ipaddress.IPv6Network("fe80::/10"),  # Link-local
        ipaddress.IPv6Network("::ffff:0:0/96"),  # IPv4-mapped IPv6
    ]

    # Dangerous hostnames that should be blocked
    DANGEROUS_HOSTNAMES: set[str] = {
        "localhost",
        "local",
        "internal",
        "intranet",
        "private",
        "corp",
        "lan",
        "home",
        "host",
        "gateway",
        "router",
    }

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        allowed_private_ips: list[str] | None = None,
        allow_private_by_default: bool = False,
    ):
        """
        Initialize URL validator.

        Args:
            allowed_domains: List of allowed domain suffixes (e.g., ["example.com"])
            allowed_private_ips: List of allowed private IP addresses
            allow_private_by_default: Whether to allow private IPs by default
        """
        self._allowed_domains = [d.lower() for d in (allowed_domains or [])]
        self._allowed_private_ips: set[str] = set()
        self._allow_private_by_default = allow_private_by_default

        # Parse and store allowed private IPs
        if allowed_private_ips:
            for ip_str in allowed_private_ips:
                try:
                    ip = ipaddress.ip_address(ip_str)
                    self._allowed_private_ips.add(str(ip))
                except ValueError:
                    # Skip invalid IP addresses
                    pass

    def validate(self, url: str | None, allow_private: bool = False) -> bool:
        """
        Validate a URL for SSRF safety.

        Args:
            url: The URL to validate
            allow_private: Whether to allow private IP addresses for this request

        Returns:
            True if the URL is valid and safe

        Raises:
            URLValidationError: If the URL is invalid or unsafe
        """
        if not url:
            raise URLValidationError("URL is required")

        if not isinstance(url, str):
            raise URLValidationError("URL must be a string")

        url = url.strip()
        if not url:
            raise URLValidationError("URL cannot be empty")

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise URLValidationError(f"Invalid URL format: {e}")

        # Check scheme
        scheme = parsed.scheme.lower()
        if scheme not in self.ALLOWED_SCHEMES:
            raise URLValidationError(f"Invalid URL scheme '{scheme}'. Only HTTP and HTTPS are allowed.")

        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            raise URLValidationError("URL must have a valid hostname")

        hostname = hostname.lower()

        # Check dangerous hostnames
        self._check_dangerous_hostname(hostname)

        # Check if domain is in whitelist (if whitelist is configured)
        if self._allowed_domains:
            if not self._is_domain_allowed(hostname):
                raise URLValidationError(f"Domain '{hostname}' is not in the allowed list")

        # Resolve and check IP address
        self._check_ip_address(hostname, allow_private)

        return True

    def _check_dangerous_hostname(self, hostname: str) -> None:
        """Check if hostname is in dangerous hostnames list."""
        # Check exact match
        if hostname in self.DANGEROUS_HOSTNAMES:
            raise URLValidationError(f"Hostname '{hostname}' is blocked (dangerous hostname)")

        # Check if hostname ends with dangerous suffix
        for dangerous in self.DANGEROUS_HOSTNAMES:
            if hostname == dangerous or hostname.endswith(f".{dangerous}"):
                raise URLValidationError(f"Hostname '{hostname}' is blocked (dangerous hostname pattern)")

    def _is_domain_allowed(self, hostname: str) -> bool:
        """Check if hostname matches any allowed domain."""
        for domain in self._allowed_domains:
            if hostname == domain or hostname.endswith(f".{domain}"):
                return True
        return False

    def _check_ip_address(self, hostname: str, allow_private: bool) -> None:
        """
        Check if hostname resolves to a private IP address.

        This method attempts to parse the hostname as an IP address.
        For domain names, we check if they're in the dangerous list.
        """
        # Try to parse as IP address (handles decimal, octal, hex representations)
        ip = self._try_parse_ip(hostname)

        if ip is None:
            # Not an IP address, it's a domain name
            # Domain validation already done in _check_dangerous_hostname
            return

        # Check if IP is in allowed private IPs whitelist
        if str(ip) in self._allowed_private_ips:
            return

        # Determine if we should allow private IPs
        should_allow_private = allow_private or self._allow_private_by_default

        if should_allow_private:
            # Still check for dangerous hostnames even with allow_private
            return

        # Check if IP is private/reserved
        if self._is_private_ip(ip):
            raise URLValidationError(f"Private IP address '{hostname}' is not allowed")

    def _try_parse_ip(self, hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
        """
        Try to parse hostname as an IP address.

        Handles various IP representations:
        - Standard dotted decimal: 192.168.1.1
        - IPv6: ::1, 2001:db8::1
        - IPv4-mapped IPv6: ::ffff:192.168.1.1
        """
        # Try standard IP parsing
        try:
            return ipaddress.ip_address(hostname)
        except ValueError:
            pass

        # Try parsing IPv4-mapped IPv6
        if hostname.startswith("[") and hostname.endswith("]"):
            # IPv6 address in brackets
            try:
                return ipaddress.ip_address(hostname[1:-1])
            except ValueError:
                pass

        # Try parsing decimal/octal/hex representations
        # These are potential bypass attempts
        try:
            # Check if it's a pure numeric string (decimal IP)
            if hostname.isdigit():
                num = int(hostname)
                if 0 <= num <= 4294967295:  # Max IPv4 value
                    return ipaddress.IPv4Address(num)

            # Check for hex representation (0x...)
            if hostname.startswith("0x") or hostname.startswith("0X"):
                num = int(hostname, 16)
                if 0 <= num <= 4294967295:
                    return ipaddress.IPv4Address(num)

            # Check for octal representation (starts with 0)
            # This is tricky - we need to be careful not to block valid domains
            # Only treat as octal if all segments are valid octal numbers
            if "." in hostname:
                parts = hostname.split(".")
                if len(parts) == 4:
                    try:
                        # Try to parse each part as octal if it starts with 0
                        octal_parts = []
                        for part in parts:
                            if part.startswith("0") and len(part) > 1:
                                octal_parts.append(int(part, 8))
                            else:
                                octal_parts.append(int(part))
                        if all(0 <= p <= 255 for p in octal_parts):
                            return ipaddress.IPv4Address(".".join(str(p) for p in octal_parts))
                    except ValueError:
                        pass

        except (ValueError, OverflowError):
            pass

        return None

    def _is_private_ip(self, ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Check if an IP address is private/reserved."""
        # Check IPv4 private ranges
        if isinstance(ip, ipaddress.IPv4Address):
            for network in self.PRIVATE_IPV4_RANGES:
                if ip in network:
                    return True

        # Check IPv6 private ranges
        if isinstance(ip, ipaddress.IPv6Address):
            for network in self.PRIVATE_IPV6_RANGES:
                if ip in network:
                    return True
            # Also check if it's an IPv4-mapped address
            if ip.ipv4_mapped:
                return self._is_private_ip(ip.ipv4_mapped)

        return False


# =============================================================================
# Pre-defined validator instances
# =============================================================================

# Quark validator: Only allows quark.cn domains
quark_validator = URLValidator(
    allowed_domains=["quark.cn"],
    allow_private_by_default=False,
)

# Emby validator: Allows private IPs with whitelist
# Note: Users should configure allowed_private_ips in production
emby_validator = URLValidator(
    allowed_domains=[],  # No domain restriction by default
    allowed_private_ips=[],  # Should be configured per deployment
    allow_private_by_default=True,  # Allow private IPs for Emby servers
)

# General validator: Blocks all private IPs and dangerous hostnames
general_validator = URLValidator(
    allowed_domains=None,  # No domain restriction
    allow_private_by_default=False,  # Block private IPs
)
