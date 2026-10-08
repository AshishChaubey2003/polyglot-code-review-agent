# Unused Imports (Ruff F401)

An import statement that is never referenced in the module adds dead weight: it slows down import time slightly, clutters the dependency list a reader has to mentally track, and can mask a typo (importing the wrong name and never noticing because nothing uses it).

```python
import os          # F401 if `os` is never referenced below
import sys


def greet(name):
    print(f"hello {name}")
```

## Fix

Remove the unused import. If the import exists only for a side effect (registering a plugin, patching a module on import), keep it but mark it explicitly so linters and readers both understand the intent:

```python
import plugin_registration  # noqa: F401  -- imported for its registration side effect
```

An import used only in type annotations under `from __future__ import annotations` is a separate case (Ruff's `TCH` rules) and should move into a `if TYPE_CHECKING:` block rather than being suppressed with `noqa`.
