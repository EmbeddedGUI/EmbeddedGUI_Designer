`ResourceGeneratorMultiTextDemo` is a small project intended for `Build -> Resource Generator...` checks when one font merges multiple `txt` files.

It includes:

- two image assets already listed in `resource/src/app_resource_config.json`
- one font entry that uses `ui_text.txt,charset.txt` so preview and edit-selection can be verified against merged text sources
- a second single-text font entry for comparison
- mirrored source assets under `.eguiproject/resources/` so project saves can sync back into `resource/src/`

Suggested checks:

1. Open [ResourceGeneratorMultiTextDemo.egui](/D:/workspace/gitee/EmbeddedGUI_Designer/examples/ResourceGeneratorMultiTextDemo/ResourceGeneratorMultiTextDemo.egui).
2. Open `Build -> Resource Generator...`.
3. Verify the sample assets load immediately.
4. Select the `ui_text` font entry and confirm the preview reflects both `ui_text.txt` and `charset.txt`.
5. Try `Edit Font Text...` and confirm Designer asks which linked `txt` file to open.
6. Run `Generate` to refresh `resource/` outputs after any edits.
