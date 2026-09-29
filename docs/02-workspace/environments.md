# Environments

## Plugin development

Local development and supported platform requirements are maintained in
[the root README](../../README.md) and [contributing](../../CONTRIBUTING.md).
Ordinary tests use temporary homes and fake worker executables.

## Dashboard prototype

[TAF-2](../01-project/backlog.md) specifies a browser application served on
localhost with synthetic examples. No production or staging deployment is
configured for it. Run commands will live beside its implementation.

## Asset-authoring resources

The user reports Blender installed on `work-station` and a connected
Higgsfield service. Reachability and specific tool capabilities have not
been verified. These are potential authoring resources, not plugin worker
backends or required runtime dependencies. The first prototype can use
primitive geometry without remote asset generation.

## Private configuration

Runtime data and credentials stay outside Git. See the
[account module](../04-modules/accounts.md) and [security policy](../../SECURITY.md).
