# Undefined Name (Ruff F821)

F821 fires when a name is referenced but was never assigned, imported, or passed as a parameter in any scope the linter can see. This is almost always a real bug, not a style preference -- the code will raise `NameError` the first time that line actually runs.

```python
def compute_total(items):
    return total + len(items)   # F821: `total` is never defined
```

Common causes:

- A variable renamed in one place but not another (`total` became `running_total` on line 3 but line 7 still says `total`).
- A typo in a variable or function name.
- Code that relies on a name being injected by `exec()`, a framework, or a notebook's global scope -- which static analysis cannot see and should generally be avoided for exactly that reason.

## Fix

Define the name before use, or correct the typo:

```python
def compute_total(items):
    total = sum(item.price for item in items)
    return total + len(items)
```

Unlike a style issue, this class of finding should never be suppressed with `noqa` without first confirming the name really is defined by something external and expected.
