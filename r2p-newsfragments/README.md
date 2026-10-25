# r2p release fragments

New r2p changes use `<issue-or-PR-number>.<category>.md` in this directory.
Categories are `packaging`, `added`, `changed`, `removed`, and `fixed`.
Write the observable change and migration impact; keep links to actual sources.
Use explicit PyO3 commit/PR links when a change is ported from upstream.

Preview the next r2p release notes without deleting fragments:

```sh
uvx towncrier build --draft --config r2p-towncrier.toml
```

The separate configuration links new fragments to r2p Issues/PRs.
Inherited `newsfragments/`, `CHANGELOG.md`, and the original towncrier configuration retain their PyO3 source and history.
