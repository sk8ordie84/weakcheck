# weakcheck (prototype)

Flags Python tests that got weaker between a commit and its first parent:
a removed test, a new unconditional skip, fewer assertions, or a loosened
tolerance argument. Conditional skips (for example "skip if an optional
dependency is missing") are listed separately, not flagged.

Static comparison of test files only. It does not prove anything about
results, and it misses weakening outside test files. Definitions and known
limits: EXPECTED.md.

    python3 weakcheck.py diff <repo> <base> <head>
    python3 weakcheck.py history <repo> --branch main
    python3 -m pytest tests

MIT licence.
