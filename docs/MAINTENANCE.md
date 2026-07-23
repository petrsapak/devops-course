# Course maintenance policy

The curriculum intentionally teaches durable concepts while its lab uses
version-pinned tools. Keeping both layers healthy requires a regular review.

## Release model

- Use dated course releases such as `2026.07`.
- Record learner-facing changes in `CHANGELOG.md`.
- Keep the previous release available as a Git tag.
- Do not silently rewrite an exercise after publishing a release.

## Quarterly review

At least once per quarter:

1. Run the repository quality workflow.
2. Build the visits-platform images and execute its tests.
3. Run `docker compose config` for both Compose combinations.
4. Run `helm lint` and render the chart.
5. Run `terraform init` and `terraform validate`.
6. Review pinned container images, Python dependencies, actions, and command
   output against their upstream release notes.
7. Check external documentation links and replace obsolete sources.
8. Complete one clean-room exercise run on Windows 11, WSL2, and Docker
   Desktop.

Patch releases may fix wording or broken commands. Changes to learning
objectives, prerequisites, grading, or lab architecture belong in a dated
course release.

## Support boundary

The maintained path is Windows 11 + WSL2 + Docker Desktop and the versions
documented in the current release. Other Linux environments will usually work,
but contributors should label platform-specific differences instead of
presenting untested commands as universal.
