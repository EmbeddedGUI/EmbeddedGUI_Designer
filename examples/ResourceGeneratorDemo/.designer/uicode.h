// GENERATED_HASH: 2e6ac0a9c37d1feb
#ifndef _UICODE_H_
#define _UICODE_H_

#include "egui.h"

/* Set up for C function definitions, even when using C++ */
#ifdef __cplusplus
extern "C" {
#endif

// Page indices
enum {
    PAGE_MAIN_PAGE = 0,
    PAGE_COUNT = 1,
};

void uicode_switch_page(int page_index);
int uicode_start_next_page(void);
int uicode_start_prev_page(void);
void uicode_create_ui(void);

/* Ends C function definitions when using C++ */
#ifdef __cplusplus
}
#endif

#endif /* _UICODE_H_ */
