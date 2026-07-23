# Contributing

Contributions that make the course more accurate, runnable, or easier to learn
are welcome.

## Before opening a change

1. Create a focused branch.
2. Preserve the lesson → exercises → test progression.
3. Explain every new command using the convention in the main README.
4. Add or update a verification step for hands-on exercises.
5. Update a test question when a learning objective changes.
6. Prefer extending `labs/visits-platform` over adding a disconnected example.

Run the local checks from the repository root:

```powershell
pwsh -File scripts/Test-Course.ps1
```

For lab application changes:

```bash
cd labs/visits-platform
python -m pip install -r requirements-dev.txt
pytest
docker compose config
```

Pull requests should describe the learner-facing problem, the change, and how
it was verified. Do not commit credentials, generated Terraform state, or
answers outside the collapsible answer keys.

By contributing, you agree that your changes use the license applicable to the
file being modified, as described in `LICENSE.md`.
