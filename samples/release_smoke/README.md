# Release Smoke Sample

`ReleaseSmokeApp` is a minimal UI Designer project used by CI to validate the
end-to-end release workflow.

The checked-in `release.json` adds:

- `USER_CFLAGS=-DEGUI_CONFIG_FUNCTION_SUPPORT_MASK=1`

This works around a current SDK-side PC link issue in the pinned SDK revision,
so the smoke build exercises the Designer release pipeline instead of failing on
an unrelated upstream configuration gap.
