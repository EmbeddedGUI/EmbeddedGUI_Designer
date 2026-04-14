`ResourceGeneratorDemo` is a small project intended for `Build -> Resource Generator...` checks.

It includes:

- two image assets already listed in `resource/src/app_resource_config.json`
- two font files plus editable UTF-8 text files for the new `Edit Font Text...` flow
- mirrored source assets under `.eguiproject/resources/` so project saves can sync back into `resource/src/`

Suggested checks:

1. Open [ResourceGeneratorDemo.egui](/D:/workspace/gitee/EmbeddedGUI_Designer/examples/ResourceGeneratorDemo/ResourceGeneratorDemo.egui).
2. Open `Build -> Resource Generator...`.
3. Verify the sample assets load immediately.
4. Select a font entry and try `Edit Font Text...`.
5. Run `Generate` to refresh `resource/` outputs after any edits.
