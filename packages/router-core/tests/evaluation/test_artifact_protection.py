import unittest

from workflow_skill_router.evaluation.artifact_protection import EncryptionAtRestArtifactProtector


class Verifier:
    def directory_is_private(self, path): return True
    def file_is_private(self, path): return True


class BadProvider:
    def encrypt(self, plaintext, digest): return plaintext, "receipt"
    def decrypt(self, ciphertext, receipt): return ciphertext
    def destroy_key(self, receipt): pass


class ArtifactProtectionTests(unittest.TestCase):
    def test_encryption_provider_cannot_claim_plaintext_is_encrypted(self):
        with self.assertRaisesRegex(RuntimeError, "encryption_protection_unverified"):
            EncryptionAtRestArtifactProtector(BadProvider(), Verifier()).protect(b"secret", "sha256:x")


if __name__ == "__main__": unittest.main()
