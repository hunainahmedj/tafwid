# Changelog

## 0.2.0

- Replace the all-purpose skill with delegate, dashboard, and settings entry points.
- Load the worker workflow only for delegation work, preserving review and handoff rules.
- Share one runtime across the three skills; preserve task state and worker history.
- Check entry-point names and packaged Markdown links in release validation.

## 0.1.1

- Simplify the title to Tafwid.
- Add a coordinated icon and cover image to the plugin listing and README.
- Validate bundled image paths and PNG signatures during package checks.

## 0.1.0

- Package the existing delegation skill and local dashboard as Tafwid.
- Add a portable Codex marketplace and plugin manifest.
- Use provider-neutral product branding, with Claude Code as the initial backend.
- Preserve legacy task switches, settings and worker history in place.
- Add installation, contributor, migration and architecture documentation.
- Add isolated CI and tagged source-release workflows.
