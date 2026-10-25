# Security reporting

r2p currently provides source delivery and best-effort maintenance.
The current maintainer is [jelven007](https://github.com/jelven007); responsibilities and publication limits are recorded in [maintainers.toml](docs/governance/maintainers.toml).

GitHub private vulnerability reporting is currently disabled.
An attempt to enable it returned HTTP 403 with the available integration credential.
A working private contact channel has not yet been established; external publication remains subject to that prerequisite.

For a potentially sensitive report, request a private reporting channel from the maintainer without including exploit details, credentials, or affected private data in a public Issue.
Once a private channel is available, provide the source SHA, environment, minimal reproduction, affected behavior, and expected impact there.
Ordinary non-sensitive defects can use the [Issue template](https://github.com/jelven007/r2p/issues/new/choose).

The [support evidence](docs/testing/evidence-summary.md) records verified environments.
Experimental introspection, async, abi3t, and WIP no_std retain their documented limits.
No response-time or security-support-period commitment has been established.
