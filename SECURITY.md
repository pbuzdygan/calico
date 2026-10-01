# Security policy

## Supported versions

Security fixes are released for the newest stable version only (image tag `:latest`). Development images (`:dev_latest`, `:devX.Y.Z`) may contain unfinished changes and are not supported.

## Reporting a vulnerability

Please do not open a public issue for security problems. Report them privately through GitHub: **Security → Report a vulnerability** in this repository. Include the affected version (image tag), steps to reproduce and the impact you expect.

You can expect a first answer within 7 days. Once a fix is released, the report is credited in `CHANGELOG.md` unless you prefer to stay anonymous.

## Scope

CALICO runs on home networks and may be exposed to the internet behind a reverse proxy with HTTPS. How it protects sign-ins and what a public instance needs (HTTPS at the reverse proxy, `FORWARDED_ALLOW_IPS`, recommended settings) is described in the "Security" section of the [README](README.md#security) – please read it before reporting. Reports about weaknesses in these protections, or hardening ideas beyond them, are welcome.
