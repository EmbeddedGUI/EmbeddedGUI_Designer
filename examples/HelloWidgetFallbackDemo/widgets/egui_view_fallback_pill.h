#ifndef _EGUI_VIEW_FALLBACK_PILL_H_
#define _EGUI_VIEW_FALLBACK_PILL_H_

#include "egui.h"
#include "widget/egui_view_button.h"

/*
 * This header intentionally uses a typedef alias instead of the SDK's
 * canonical `typedef struct egui_view_xxx egui_view_xxx_t;` pattern.
 * The Designer parser skips it, and the project-level Python descriptor in
 * custom_widgets/fallback_pill.py provides the manual fallback metadata.
 */
typedef egui_view_button_t egui_view_fallback_pill_t;

void egui_view_fallback_pill_init(egui_view_t *self);
void egui_view_fallback_pill_set_text(egui_view_t *self, const char *text);
void egui_view_fallback_pill_set_emphasis(egui_view_t *self, uint8_t emphasis);

#endif /* _EGUI_VIEW_FALLBACK_PILL_H_ */
