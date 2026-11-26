/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
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

static void test_surface_row(void)
{
	static const u16 base[] = { 0, 0xe2, 0xea, 0xe9, 0, 0x70, 0x6f,
				    0x46, 0x4a, 0x4d, 0x4b, 0x4e };
	bool eject, mic, light;
	u16 media;
	u8 out[DENALI_KBD_OUT_SIZE];

	for (unsigned i = 0; i < 12; i++) {
		struct denali_hhkb s = { 0 };
		u8 f = 0x3a + i;

		/* Old Fn / Fn Lock sent a physical F usage; normalize it to base. */
		assert(denali_hhkb_snapshot(&s, REPORT(0, f)));
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		assert(out[2] == (i >= 7 ? base[i] : 0));
		assert(media == (i < 7 ? base[i] : 0));
		assert(mic == (i == 0) && light == (i == 4));
		assert(denali_hhkb_snapshot(&s, REPORT(0, 0x4f)));
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		/* New Fn with the base report, across all on-wire report classes. */
		if (i == 0 || i == 4)
			denali_hhkb_top_button(&s, i, true);
		else if (i < 7)
			denali_hhkb_consumer(&s, base[i]);
		else
			assert(denali_hhkb_snapshot(&s, REPORT(0, 0x4f, base[i])));
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		assert(out[2] == f && out[3] == 0 && !mic && !light && !media);
		/* Fn first up preserves the F-key until its own release. */
		assert(denali_hhkb_snapshot(&s, REPORT(0, i >= 7 ? base[i] : 0)));
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		assert(out[2] == f);
		assert(denali_hhkb_snapshot(&s, REPORT(0)));
		denali_hhkb_consumer(&s, 0);
		denali_hhkb_top_button(&s, 0, false);
		denali_hhkb_top_button(&s, 4, false);
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		assert(!out[2] && !mic && !light && !media);
		/* With new Fn down, firmware's old-Fn variant is still the
		 * same physical position. Release that position before Fn.
		 */
		assert(denali_hhkb_snapshot(&s, REPORT(0, 0x4f, f)));
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		assert(out[2] == f);
		assert(denali_hhkb_snapshot(&s, REPORT(0, 0x4f)));
		denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
		assert(!out[2] && !mic && !light && !media);
	}
	struct denali_hhkb s = { 0 };
	assert(denali_hhkb_snapshot(&s, REPORT(0, 0x4f, 0x1e, 0x42)));
	denali_hhkb_top_button(&s, 0, true);
	denali_hhkb_consumer(&s, 0x00cd); /* Unrelated Play/Pause passes. */
	denali_hhkb_outputs(&s, out, &eject, &mic, &light, &media);
	assert(out[2] == 0x3a && out[3] == 0x42 && out[4] == 0 && media == 0xcd);
}

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
	test_surface_row();
	return 0;
}
