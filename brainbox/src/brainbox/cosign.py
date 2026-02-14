"""Cosign image signature verification.

Wraps the ``cosign verify`` CLI to check container image signatures against
a public key.  Follows the same subprocess pattern as ``secrets.py``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CosignResult:
    """Outcome of a ``cosign verify`` invocation."""

    verified: bool
    image_ref: str
    stdout: str
    stderr: str


class CosignVerificationError(RuntimeError):
    """Raised when signature verification fails in enforce mode."""

    def __init__(self, result: CosignResult) -> None:
        self.result = result
        super().__init__(
            f"Image signature verification failed for {result.image_ref}: {result.stderr}"
        )


def _cosign_run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a ``cosign`` CLI command.

    Returns the completed process regardless of exit code — callers decide
    whether to treat non-zero as an error based on the configured mode.

    Raises ``FileNotFoundError`` with a helpful message if cosign is not
    installed.
    """
    try:
        return subprocess.run(
            ["cosign", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            "cosign binary not found — install it from https://docs.sigstore.dev/cosign/system_config/installation/"
        ) from None


def verify_image_keyless(
    image_ref: str,
    certificate_identity: str,
    oidc_issuer: str,
    repo_digests: list[str],
) -> CosignResult:
    """Verify an image using keyless/OIDC identity (Sigstore Fulcio + Rekor).

    *certificate_identity* is matched as a regexp against the certificate's
    subject identity.  *oidc_issuer* must match the OIDC issuer that minted
    the signing certificate (e.g. ``https://token.actions.githubusercontent.com``).

    Raises ``ValueError`` when *repo_digests* is empty.
    """
    if not repo_digests:
        raise ValueError(
            f"Image '{image_ref}' has no repo digests — "
            "it appears to be a local-only image that was never pushed to a registry"
        )

    digest_ref = repo_digests[0]
    result = _cosign_run(
        [
            "verify",
            "--certificate-identity-regexp",
            certificate_identity,
            "--certificate-oidc-issuer",
            oidc_issuer,
            digest_ref,
        ]
    )

    return CosignResult(
        verified=result.returncode == 0,
        image_ref=digest_ref,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def verify_image(
    image_ref: str,
    key_path: str,
    repo_digests: list[str],
) -> CosignResult:
    """Verify an image signature using ``cosign verify --key``.

    *repo_digests* should come from the Docker image's ``RepoDigests``
    attribute.  The first digest is used as the verification target so that
    cosign validates the exact content-addressable image.

    Raises ``ValueError`` when *repo_digests* is empty (local-only image
    with no registry digest).
    """
    if not repo_digests:
        raise ValueError(
            f"Image '{image_ref}' has no repo digests — "
            "it appears to be a local-only image that was never pushed to a registry"
        )

    digest_ref = repo_digests[0]
    result = _cosign_run(["verify", "--key", key_path, digest_ref])

    return CosignResult(
        verified=result.returncode == 0,
        image_ref=digest_ref,
        stdout=result.stdout,
        stderr=result.stderr,
    )
