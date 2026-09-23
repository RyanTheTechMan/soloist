"""Store a user's Soloist API key in the platform credential store.

Only macOS Keychain is exercised by this package. Python keyring also supports
Windows Credential Locker and common Linux desktop secret stores for future
ports; those platforms still need runtime validation before release.
"""
import platform

SERVICE = "local.soloistcompat.runtime"
ACCOUNT = "soloist-api-key"


class CredentialError(ValueError):
    """Fixed text only: callers may print this without revealing the key."""


def validate(secret):
    if isinstance(secret, bytes):
        try:
            secret = secret.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CredentialError("API key must be UTF-8 text") from error
    if not isinstance(secret, str) or not 1 <= len(secret.encode("utf-8")) <= 4096 or any(
        char in secret for char in ("\0", "\n", "\r")) or secret != secret.strip():
        raise CredentialError("API key must be one nonempty line, at most 4096 bytes")
    return secret


def backend():
    import keyring
    if platform.system() == "Darwin":
        from keyring.backends.macOS import Keyring
        keyring.set_keyring(Keyring())
    selected = keyring.get_keyring()
    if selected.priority <= 0:
        raise CredentialError("No secure system credential store is available")
    return keyring


def save(secret):
    backend().set_password(SERVICE, ACCOUNT, validate(secret))


def load():
    value = backend().get_password(SERVICE, ACCOUNT)
    if value is None:
        raise CredentialError("No Soloist API key is saved in the system credential store")
    return validate(value)


def exists():
    return backend().get_password(SERVICE, ACCOUNT) is not None
