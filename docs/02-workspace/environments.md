# Environments

## Plugin development

Local development and supported platform requirements are maintained in
[the root README](../../README.md) and [contributing](../../CONTRIBUTING.md).
Ordinary tests use temporary homes and fake worker executables.

## Dashboard prototype

[TAF-2](../01-project/backlog.md) specifies a browser application served on
localhost with synthetic examples. No production or staging deployment is
configured for it. Run commands live in the [prototype README](../../prototypes/agent-office/README.md).

## Asset-authoring resources

Verified on 2026-10-03: `work-station` accepts non-interactive SSH from the
Mac and lands in WSL2. From there, Windows Blender 5.1.1 runs headless
(`blender.exe -b`) and Cycles sees the RTX 5090 through OptiX. The
[agent world](../04-modules/dashboard.md) builds its environment packages
this way. Builds read and write under `C:\tafwid-art` (`/mnt/c/tafwid-art`
in WSL). The user also reports ComfyUI 3D workflows and a Higgsfield
service; neither is used yet. None of these are plugin worker backends or
runtime dependencies: the committed packages run without them.

## Private configuration

Runtime data and credentials stay outside Git. See the
[account module](../04-modules/accounts.md) and [security policy](../../SECURITY.md).
