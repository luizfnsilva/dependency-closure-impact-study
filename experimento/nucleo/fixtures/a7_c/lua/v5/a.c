#include "a.h"
#include "u.h"
#ifndef V_EXTRA
#define V_EXTRA 0
#endif
int fa(int x) { return x * A_VAL + U_VAL + V_EXTRA; }
