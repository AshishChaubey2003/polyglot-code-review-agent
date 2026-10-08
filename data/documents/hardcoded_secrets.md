# Hardcoded Secrets and Credentials (CWE-798)

Hardcoding a password, API key, or token directly in source code means the secret ships with the code: it ends up in version control history, in anyone who can read the repository, and in any log that happens to print the variable.

```python
password = "SuperSecret123!"          # vulnerable
API_KEY = "sk-abc123..."              # vulnerable
```

## Prevention

Load secrets from the environment at runtime instead of writing them into source:

```python
import os
password = os.getenv("APP_PASSWORD")
```

For local development, `.env` files loaded via `python-dotenv` keep the secret out of the committed code; `.env` itself must be listed in `.gitignore`. In production, the equivalent is environment variables injected by the deployment platform (Streamlit Cloud secrets, a container's env vars, or a secrets manager).

## Why rotation matters

Removing a hardcoded secret from the current version of a file does not remove it from git history. A secret that was ever committed should be treated as compromised and rotated (regenerated at the provider), not just deleted from the latest commit.
