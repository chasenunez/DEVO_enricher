# Contributing to make_icsv


Thanks for your interest in contributing! We welcome bug reports, feature requests, documentation improvements, and pull requests. This document explains how to contribute and what to expect.


## How to contribute


### 1) Report an issue
- Open an issue describing the problem or feature request. Include steps to reproduce (for bugs), sample input, expected output, and actual output.
- If you can, include a minimal example CSV that reproduces the issue.


### 2) Discuss before large changes
For large or architectural changes (new major features, data model changes), please open an issue first to discuss design and trade-offs. This avoids wasted work and keeps the project consistent.


### 3) Fork & create a branch
- Fork the repository.
- Create a topic branch: `git checkout -b feature/my-new-feature` or `fix/bug-xyz`.


### 4) Write tests
- Add tests for bugs and new features under the `tests/` directory using `pytest`.
- Tests should be deterministic and fast.


### 5) Linting & style
- Follow idiomatic Python (PEP8). We recommend using `black` for formatting and `flake8` for linting, but this repository does not enforce them by default.
- Keep functions small and well-documented.


### 6) Commit messages
- Use clear, concise messages. Example:
- `feat: add automatic timezone detection`
- `fix: handle missing header line gracefully`
- `docs: update README examples`


### 7) Open a pull request
- Target the `main` branch (or the branch documented in the repo).
- In the PR description, explain the change, reference relevant issues, and include examples or screenshots if applicable.
- Keep PRs small and focused when possible.


## Review process
- Maintainers will review PRs. Expect constructive feedback; we may ask for changes.
- Tests should pass before merging. If you need help, respond to review comments and maintainers will guide you.


## Code of Conduct
By participating, you agree to abide by the project's Code of Conduct. Be respectful and constructive in discussions.


## License
Contributions are accepted under the project's license. By submitting a PR you agree to license your contribution under the same license.


## Contact
If you have questions about contributing or want to propose major changes, open an issue or contact the maintainers directly.