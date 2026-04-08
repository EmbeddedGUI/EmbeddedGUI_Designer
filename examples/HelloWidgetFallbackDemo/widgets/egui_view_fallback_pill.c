#include "egui.h"
#include "widgets/egui_view_fallback_pill.h"
#include "background/egui_background_color.h"

EGUI_BACKGROUND_COLOR_PARAM_INIT_ROUND_RECTANGLE_STROKE(bg_fallback_pill_idle_param, EGUI_COLOR_LIGHT_GREY, EGUI_ALPHA_100, 18, 1, EGUI_COLOR_DARK_GREY, EGUI_ALPHA_100);
EGUI_BACKGROUND_COLOR_STATIC_CONST_INIT(bg_fallback_pill_idle, (const egui_background_params_t *)&bg_fallback_pill_idle_param);

EGUI_BACKGROUND_COLOR_PARAM_INIT_ROUND_RECTANGLE_STROKE(bg_fallback_pill_emphasis_param, EGUI_COLOR_BLUE, EGUI_ALPHA_100, 18, 1, EGUI_COLOR_NAVY, EGUI_ALPHA_100);
EGUI_BACKGROUND_COLOR_STATIC_CONST_INIT(bg_fallback_pill_emphasis, (const egui_background_params_t *)&bg_fallback_pill_emphasis_param);

static void egui_view_fallback_pill_apply_emphasis(egui_view_t *self, uint8_t emphasis)
{
    if (emphasis)
    {
        egui_view_set_background(self, EGUI_BG_OF(&bg_fallback_pill_emphasis));
        egui_view_label_set_font_color(self, EGUI_COLOR_WHITE, EGUI_ALPHA_100);
        return;
    }

    egui_view_set_background(self, EGUI_BG_OF(&bg_fallback_pill_idle));
    egui_view_label_set_font_color(self, EGUI_COLOR_BLACK, EGUI_ALPHA_100);
}

void egui_view_fallback_pill_init(egui_view_t *self)
{
    egui_view_button_init(self);
    egui_view_label_set_text(self, "Fallback pill");
    egui_view_label_set_align_type(self, EGUI_ALIGN_CENTER);
    egui_view_set_padding(self, 12, 12, 6, 6);
    egui_view_set_clickable(self, 0);
    egui_view_fallback_pill_apply_emphasis(self, 0);
}

void egui_view_fallback_pill_set_text(egui_view_t *self, const char *text)
{
    egui_view_label_set_text(self, text);
}

void egui_view_fallback_pill_set_emphasis(egui_view_t *self, uint8_t emphasis)
{
    egui_view_fallback_pill_apply_emphasis(self, emphasis);
}
