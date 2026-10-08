# Unsafe eval/exec Usage (CWE-95, Bandit B307)

`eval()` and `exec()` run arbitrary Python source from a string at runtime. If any part of that string is influenced by untrusted input, the caller has effectively given the input full code execution.

```python
def run_expression(user_input):
    return eval(user_input)          # vulnerable: user_input can be any Python expression
```

An input like `__import__('os').system('rm -rf /')` is a valid Python expression and will execute.

## Safer alternatives

- For evaluating a literal (a number, list, dict, tuple, string) from text, use `ast.literal_eval()`, which only parses Python literals and refuses to execute arbitrary expressions.
- For a small, fixed set of operations (like a calculator), use a real parser (e.g. the `ast` module walked manually, or a small grammar) restricted to the operators you intend to support, rather than a general-purpose `eval`.
- If dynamic dispatch is the actual need ("call the function named by this string"), use a lookup dictionary of known, explicitly allowed callables instead of `eval`/`exec`/`getattr` on arbitrary names.

`exec()` carries the same risk for statements (assignments, imports, loops) rather than expressions, and should be avoided on anything not fully controlled by the developer.
