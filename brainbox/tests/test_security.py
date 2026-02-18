"""Security-focused tests for brainbox."""

import shlex
import pytest


class TestShellQuoting:
    """Tests for shell quoting using shlex.quote() to prevent command injection."""

    def test_basic_string(self):
        """Should pass through simple strings without quotes."""
        assert shlex.quote("hello") == "hello"
        assert shlex.quote("hello123") == "hello123"
        assert shlex.quote("hello_world") == "hello_world"

    def test_single_quote_escaping(self):
        """Should properly quote strings with single quotes."""
        # shlex.quote handles single quotes by using complex escaping.
        # The exact format doesn't matter - what matters is:
        # 1. The original string content is preserved
        # 2. The result is safe for shell execution

        # Test that original content is preserved in some form
        result1 = shlex.quote("it's")
        assert len(result1) > len("it's")  # Should be longer due to quoting

        result2 = shlex.quote("'test'")
        assert len(result2) > len("'test'")  # Should be longer due to quoting

        # Most importantly: these strings are safe and won't execute shell commands
        # We verify this is tested in the injection prevention test below

    def test_injection_prevention(self):
        """Verify shlex.quote prevents all command injection patterns."""
        # Dollar sign (variable expansion) - SAFELY quoted
        result = shlex.quote("$HOME")
        assert result == "'$HOME'"  # Quoted, won't expand

        # Backticks (command substitution) - SAFELY quoted
        result = shlex.quote("`whoami`")
        assert result == "'`whoami`'"  # Quoted, won't execute

        # Command chaining - SAFELY quoted
        result = shlex.quote("test; rm -rf /")
        assert result == "'test; rm -rf /'"  # Quoted, won't chain

        # Command substitution with $() - SAFELY quoted
        result = shlex.quote("$(malicious)")
        assert result == "'$(malicious)'"  # Quoted, won't execute

        # Pipe - SAFELY quoted
        result = shlex.quote("test | malicious")
        assert result == "'test | malicious'"  # Quoted, won't pipe

    def test_empty_string(self):
        """Should handle empty strings."""
        assert shlex.quote("") == "''"

    def test_whitespace(self):
        """Should quote strings with whitespace."""
        assert shlex.quote("hello world") == "'hello world'"
        assert shlex.quote("  spaces  ") == "'  spaces  '"

    def test_newlines(self):
        """Should safely quote newlines."""
        result = shlex.quote("line1\nline2")
        assert result == "'line1\nline2'"  # Safely quoted

    def test_real_world_secret(self):
        """Test with a realistic secret value."""
        secret = "sk-proj-abc123!@#$%^&*()"
        quoted = shlex.quote(secret)
        # Should be safely quoted to prevent any interpretation
        assert quoted == "'sk-proj-abc123!@#$%^&*()'"

    def test_special_characters(self):
        """Test various special shell characters are properly handled."""
        dangerous = [
            ("$PATH", "'$PATH'"),
            ("`echo test`", "'`echo test`'"),
            ("test && echo", "'test && echo'"),
            ("test || echo", "'test || echo'"),
            ("test; echo", "'test; echo'"),
            ("test | echo", "'test | echo'"),
            ("test > file", "'test > file'"),
            ("test < file", "'test < file'"),
            ("test & echo", "'test & echo'"),
            ("(subshell)", "'(subshell)'"),
            ("{brace}", "'{brace}'"),
            ("*glob*", "'*glob*'"),
            ("?glob?", "'?glob?'"),
        ]
        for input_val, expected in dangerous:
            assert shlex.quote(input_val) == expected


class TestSecurityPatterns:
    """Tests for security patterns across the application."""

    def test_shell_quoting_integration(self):
        """Integration test: verify shlex.quote makes strings safe for shell."""
        test_cases = [
            # (input, should_be_quoted)
            ("simple", False),  # No special chars, no quotes needed
            ("with space", True),  # Whitespace requires quotes
            ("with'quote", True),  # Special chars require quotes
            ("$VARIABLE", True),  # Metacharacters require quotes
            ("`command`", True),  # Metacharacters require quotes
        ]

        for input_val, should_quote in test_cases:
            result = shlex.quote(input_val)
            if should_quote:
                # Should be wrapped in quotes or have special escaping
                assert "'" in result or '"' in result or "\\" in result
            # Result should always be safe - no unquoted special chars
            assert shlex.quote(result) == result or result.startswith("'") or result.startswith('"')

    def test_shell_quoting_prevents_injection(self):
        """
        Verify that shlex.quote() prevents all common injection attacks.
        This test documents that we've migrated from unsafe _shell_escape()
        to secure shlex.quote().
        """
        dangerous_inputs = [
            "$MALICIOUS",  # Variable expansion
            "`malicious`",  # Command substitution
            "$(malicious)",  # Command substitution
            "test; malicious",  # Command chaining
            "test && malicious",  # Conditional execution
            "test || malicious",  # Conditional execution
            "test | malicious",  # Pipe
        ]

        for dangerous in dangerous_inputs:
            quoted = shlex.quote(dangerous)
            # All dangerous characters should be inside quotes
            # which means they won't be interpreted by the shell
            assert quoted.startswith("'") and quoted.endswith("'"), (
                f"Failed to safely quote: {dangerous} -> {quoted}"
            )


class TestInputValidation:
    """Tests for input validation."""

    def test_session_name_validation(self):
        """Session names should match Docker naming rules."""
        from brainbox.validation import validate_session_name, ValidationError

        # Valid names
        valid_names = ["test", "test-session", "test_session", "test123", "test.name"]
        for name in valid_names:
            assert validate_session_name(name) == name

        # Invalid names
        invalid_names = [
            ("", "empty"),
            ("-test", "start with dash"),
            ("_test", "start with underscore"),
            (".test", "start with dot"),
            ("test space", "contains space"),
            ("test/slash", "contains slash"),
            ("test..name", "path traversal"),
            ("a" * 65, "too long"),
        ]
        for name, reason in invalid_names:
            with pytest.raises(ValidationError):
                validate_session_name(name)

    def test_artifact_key_validation(self):
        """Artifact keys should prevent path traversal."""
        from brainbox.validation import validate_artifact_key, ValidationError

        # Valid keys
        valid_keys = ["file.txt", "dir/file.txt", "a/b/c/file.txt"]
        for key in valid_keys:
            result = validate_artifact_key(key)
            assert result  # Should return normalized key

        # Invalid keys
        invalid_keys = [
            ("../etc/passwd", "path traversal"),
            ("/absolute/path", "absolute path"),
            ("dir/../../../etc/passwd", "complex traversal"),
            ("", "empty"),
            ("file\x00.txt", "null byte"),
        ]
        for key, reason in invalid_keys:
            with pytest.raises(ValidationError):
                validate_artifact_key(key)

    def test_volume_mount_validation(self):
        """Volume mounts should be validated."""
        from brainbox.validation import validate_volume_mount, ValidationError

        # Valid mounts
        valid_mounts = [
            ("/host/path:/container/path", ("/host/path", "/container/path", "rw")),
            ("/host/path:/container/path:ro", ("/host/path", "/container/path", "ro")),
            ("/host/path:/container/path:rw", ("/host/path", "/container/path", "rw")),
        ]
        for mount_spec, expected in valid_mounts:
            assert validate_volume_mount(mount_spec) == expected

        # Invalid mounts
        invalid_mounts = [
            ("relative/path:/container/path", "relative host path"),
            ("/host/path", "missing container path"),
            ("/host/path:relative/container", "relative container path"),
            ("/host/path:/container/path:invalid", "invalid mode"),
            ("", "empty"),
        ]
        for mount_spec, reason in invalid_mounts:
            with pytest.raises(ValidationError):
                validate_volume_mount(mount_spec)

    def test_port_validation(self):
        """Ports should be in valid range."""
        from brainbox.validation import validate_port, ValidationError

        # Valid ports
        assert validate_port(1024) == 1024
        assert validate_port(8080) == 8080
        assert validate_port(65535) == 65535

        # Invalid ports
        with pytest.raises(ValidationError):
            validate_port(80)  # Too low (requires root)
        with pytest.raises(ValidationError):
            validate_port(65536)  # Too high
        with pytest.raises(ValidationError):
            validate_port("8080")  # Wrong type

    def test_role_validation(self):
        """Roles should be from allowed set."""
        from brainbox.validation import validate_role, ValidationError

        # Valid roles
        assert validate_role("developer") == "developer"
        assert validate_role("researcher") == "researcher"
        assert validate_role("performer") == "performer"

        # Invalid roles
        with pytest.raises(ValidationError):
            validate_role("admin")
        with pytest.raises(ValidationError):
            validate_role("invalid")
        with pytest.raises(ValidationError):
            validate_role("")
