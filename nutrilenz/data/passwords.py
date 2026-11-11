import hashlib
import hmac
import secrets


class PasswordHasher:
    """Hashes passwords with salted PBKDF2-SHA256. Plain passwords are never stored."""

    ALGORITHM = "pbkdf2_sha256"

    def __init__(self, iterations: int = 200_000):
        self._iterations = iterations

    def hash(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = self._digest(password, salt, self._iterations)
        return f"{self.ALGORITHM}${self._iterations}${salt}${digest}"

    def verify(self, password: str, stored: str) -> bool:
        try:
            algorithm, iterations, salt, digest = stored.split("$")
            if algorithm != self.ALGORITHM:
                return False
            expected = self._digest(password, salt, int(iterations))
        except (ValueError, AttributeError):
            return False
        return hmac.compare_digest(expected, digest)     # same time for right and wrong guesses

    @staticmethod
    def _digest(password: str, salt: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   salt.encode("utf-8"), iterations).hex()
