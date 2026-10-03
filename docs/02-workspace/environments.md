# Environments

## Plugin development

Local development and supported platform requirements are maintained in
[the root README](../../README.md) and [contributing](../../CONTRIBUTING.md).
Ordinary tests use temporary homes and fake worker executables.

## Dashboard prototypes

The [agent world](../../prototypes/agent-world/README.md)
([TAF-7](../01-project/backlog.md)) is the current dashboard prototype. It
is a browser application served on localhost with synthetic examples, and
its README owns run commands. The dev server may also be exposed inside
the user's tailnet with Tailscale Serve; nothing is deployed publicly, and
there is no production or staging target. The first prototype,
[agent office](../../prototypes/agent-office/README.md)
([TAF-2](../01-project/backlog.md)), remains as a reference.

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
