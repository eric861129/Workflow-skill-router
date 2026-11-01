# Third-party notices

The shipped MCP bundle contains the following runtime libraries:

| Package | Version | License | Purpose |
| --- | --- | --- | --- |
| `@modelcontextprotocol/sdk` | 1.32.2 | MIT | MCP server transport and protocol implementation |
| `zod` | 4.6.7 | MIT | Runtime input validation |

`esbuild` 0.28.2 (MIT) is used only to produce the deterministic MCP bundle and is not shipped as a standalone runtime dependency.

Copyright and license texts for these projects remain governed by their upstream distributions. The generated SPDX SBOM records the exact versions and marks `esbuild` as a build tool.
