`ResourceGeneratorDemo` is a small project intended for `Build -> Resource Generator...` checks in the common single-text font workflow.

It includes:

- two image assets already listed in `resource/src/app_resource_config.json`
- two font files plus editable UTF-8 text files for the new `Edit Font Text...` flow
- mirrored source assets under `.eguiproject/resources/` so project saves can sync back into `resource/src/`

If you need to verify a font entry that merges multiple `txt` files, use `ResourceGeneratorMultiTextDemo` instead so that scenario stays isolated.

Suggested checks:

1. Open [ResourceGeneratorDemo.egui](/D:/workspace/gitee/EmbeddedGUI_Designer/examples/ResourceGeneratorDemo/ResourceGeneratorDemo.egui).
2. Open `Build -> Resource Generator...`.
3. Verify the sample assets load immediately.
4. Select a font entry and try `Edit Font Text...`.
5. Run `Generate` to refresh `resource/` outputs after any edits.
