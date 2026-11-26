/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef uint8_t u8;
#include "denali_hhkb.h"

static void expect(struct denali_hhkb *s, const u8 *in, const u8 *expected, bool eject)
{
	u8 out[DENALI_KBD_SIZE];
	bool want_eject;

	memset(out, 0xa5, sizeof(out));
	assert(denali_hhkb_translate(s, in, out, &want_eject));
	assert(!memcmp(expected, out, sizeof(out)));
	assert(want_eject == eject);
}

#define REPORT(...) ((const u8[DENALI_KBD_SIZE]){ 1, __VA_ARGS__ })

int main(void)
{
	static const u8 layer[][2] = {
		{0x04,0x81}, {0x07,0x7f}, {0x09,0xff}, {0x0b,0x55}, {0x0c,0x46},
		{0x0d,0x54}, {0x0e,0x4a}, {0x0f,0x4b}, {0x10,0x56}, {0x11,0x57},
		{0x12,0x47}, {0x13,0x48}, {0x16,0x80}, {0x28,0x58}, {0x29,0x66},
		{0x2a,0x53}, {0x2b,0x39}, {0x2d,0x44}, {0x2e,0x45}, {0x2f,0x52},
		{0x31,0x49}, {0x33,0x50}, {0x34,0x4f}, {0x35,0x4c}, {0x36,0x4d},
		{0x37,0x4e}, {0x38,0x51},
	};
	struct denali_hhkb s = { 0 };
	bool eject;
	u8 out[12];

	for (unsigned i = 0; i < sizeof(layer) / sizeof(layer[0]); i++) {
		u8 from = layer[i][0], to = layer[i][1];
		expect(&s, REPORT(0, from), REPORT(0, from), false);
		expect(&s, REPORT(0), REPORT(0), false);
		expect(&s, REPORT(0, 0x4f, from), REPORT(0, to == 0xff ? 0 : to), to == 0xff);
		/* Releasing Fn before the mapped key never leaks the unmodified key. */
		expect(&s, REPORT(0, from), REPORT(0, to == 0xff ? 0 : to), to == 0xff);
		expect(&s, REPORT(0), REPORT(0), false);
	}
	for (u8 i = 0; i < 10; i++) {
		expect(&s, REPORT(0, 0x1e + i), REPORT(0, 0x1e + i), false);
		expect(&s, REPORT(0), REPORT(0), false);
		expect(&s, REPORT(0, 0x4f, 0x1e + i), REPORT(0, 0x3a + i), false);
		expect(&s, REPORT(0), REPORT(0), false);
	}
	expect(&s, REPORT(0x01, 0x50, 0x51, 0x52), REPORT(0), false);
	expect(&s, REPORT(0x03, 0x39, 0x04), REPORT(0x03, 0x04), false);
	expect(&s, REPORT(0x04), REPORT(0x08), false);
	expect(&s, REPORT(0x08), REPORT(0x04), false);
	expect(&s, REPORT(0, 0x33), REPORT(0, 0x33), false);
	expect(&s, REPORT(0, 0x4f, 0x33, 0x34), REPORT(0, 0x33, 0x4f), false);
	assert(!denali_hhkb_translate(&s, REPORT(0, 1), out, &eject));
	assert(!denali_hhkb_translate(&s, REPORT(0, 0xff), out, &eject));
	expect(&s, REPORT(0, 0x34, 0x34), REPORT(0, 0x4f), false);
	expect(&s, REPORT(0), REPORT(0), false);
	return 0;
}
