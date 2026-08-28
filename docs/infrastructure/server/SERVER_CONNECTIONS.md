# Server Connection Contract

The platform server layer models a remote host as an explicit `server_id` plus a complete connection/runtime profile. It does not ship with a fleet catalogue.

A deployment or downstream project selects its own server IDs and provides profile values outside the reusable source tree. The platform parses and validates those values; it does not guess hostnames, users, ports, paths, toolchains, or credentials.

## Profile naming

For a server ID such as `server-a`, the environment prefix is derived mechanically as `RP_SERVER_SERVER_A_...`. Fleet membership is explicit through `RP_SERVER_CATALOG_IDS`.

The checked-in example [`../../../configs/server_profiles/server.example.env`](../../../configs/server_profiles/server.example.env) documents the supported fields without selecting any real machine.

## Authentication

Prefer an SSH key or agent for unattended operations. Passwords and private keys are never committed. Local SSH configuration and control-socket paths remain operator-local.
## Runtime and path identity

Remote filesystem roots, interpreter/toolchain paths, session configuration, and repository roots are part of the deployment profile because they affect reproducibility and mutation safety. A downstream deployment may pin executable digests when exact toolchain attestation is required.

Command execution, file transfer, repository operations, and persistent sessions have independent timeout/budget controls. Server operations are journaled with typed observation/mutation intent so retries do not silently duplicate uncertain external effects.

## Repository boundary

Concrete machine inventories and their current state belong in the downstream deployment repository or an ignored operator inventory. They must not be added to this upstream document, the generic README, or the platform release manifest.
