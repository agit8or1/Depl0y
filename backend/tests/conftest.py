"""Point every test at a throwaway SQLite database.

Set before any `app.*` import so the engine in app.core.database can never be
bound to the real /var/lib/depl0y database, whatever DATABASE_URL says, and so
importing app.main logs to a temp file instead of /var/log/depl0y.
"""
import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="depl0y-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_DIR}/test.db"
os.environ["LOG_FILE"] = f"{_TEST_DB_DIR}/app.log"
os.environ["DEPL0Y_SSH_KNOWN_HOSTS"] = f"{_TEST_DB_DIR}/ssh/known_hosts"
# Keep _persistent_secret's generated key files out of /var/lib/depl0y.
os.environ["DEPL0Y_KEY_DIR"] = f"{_TEST_DB_DIR}/keys"
