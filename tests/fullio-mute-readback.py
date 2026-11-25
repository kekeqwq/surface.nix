#!/usr/bin/env python3
"""Exercise FullIO mute readback and amplifier pairing from patched kernel sources."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


PREAMBLE = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int64_t s64;
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 0x01
#define U64_MAX UINT64_MAX
#define EXPORT_SYMBOL_GPL(sym)
#define READ_ONCE(x) (x)
#define spin_lock_irqsave(lock, flags) ((void)(lock), (flags) = 0)
#define spin_unlock_irqrestore(lock, flags) ((void)(lock), (void)(flags))
#define BIT(n) (1u << (n))
#define ALIGN(n, a) (((n) + (a) - 1) & ~((a) - 1))
#define APM_MODULE_PARAM_DATA_SIZE 16

struct gpr_resp_pkt { const u8 *payload; int payload_size; };
struct q6apm_fullio_get { u32 instance, param; size_t bytes; void *data; };
struct q6apm {
    unsigned long fullio_transport;
    u64 fullio_transport_epoch;
    int fullio_oob_lock;
};
struct q6apm_graph {
    struct q6apm *apm;
    u64 fullio_mute_epoch, fullio_mute_transport_epoch;
    bool fullio_mute_verified;
};
struct device { struct device *parent; struct q6apm *apm; bool *of_node; };
#define dev_get_drvdata(dev) ((dev)->apm)
#define set_bit(bit, p) (*(p) |= BIT(bit))
#define clear_bit(bit, p) (*(p) &= ~BIT(bit))
enum q6apm_fullio_feedback { Q6APM_FULLIO_VI, Q6APM_FULLIO_CPS };

struct snd_soc_card;
struct snd_soc_component {
    struct snd_soc_card *card;
    const char *name_prefix;
    void *dev;
};
struct snd_soc_dai { struct snd_soc_component *component; };
struct snd_soc_dai_link { const char *name; };
struct snd_soc_pcm_runtime {
    struct snd_soc_dai_link *dai_link;
    struct snd_soc_dai *codecs;
    int ncodecs;
    struct snd_soc_card *card;
};
struct snd_soc_card {
    struct snd_soc_pcm_runtime *runtimes;
    size_t nruntimes;
    struct device *dev;
};
#define for_each_card_rtds(card, rtd) \
    for ((rtd) = (card)->runtimes; (rtd) < (card)->runtimes + (card)->nruntimes; (rtd)++)
#define for_each_rtd_codec_dais(rtd, i, codec) \
    for ((i) = 0; (i) < (rtd)->ncodecs && ((codec) = &(rtd)->codecs[i]); (i)++)

static u32 get_unaligned_le32(const u8 *p)
{
    return (u32)p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24;
}

static void put_word(u8 *p, unsigned int index, u32 value)
{
    for (unsigned int i = 0; i < 4; i++)
        p[index * 4 + i] = value >> (8 * i);
}
"""

PA_CHECK_STUB = r"""
#define __maybe_unused
#define SNDRV_PCM_STREAM_PLAYBACK 0
struct q6apm_dai_rtd { struct q6apm_graph *graph; };
struct snd_pcm_runtime { void *private_data; };
struct snd_pcm_substream {
    struct snd_pcm_runtime *runtime;
    struct snd_soc_pcm_runtime *rtd;
    int stream;
};
#define snd_soc_substream_to_rtd(s) ((s)->rtd)
#define of_machine_is_compatible(s) (!strcmp(s, "microsoft,denali"))
#define of_property_read_bool(node, s) (*(node) && !strcmp(s, "microsoft,denali-fullio-post-pa-test"))

struct fake_amp { s64 epoch; int fail; };
static int pa_checks, epoch_change_after;
static int wsa884x_fullio_pa_ready(struct snd_soc_component *component, s64 *epoch)
{
    struct fake_amp *a = component->dev;
    if (++pa_checks == epoch_change_after)
        a->epoch++;
    if (a->fail)
        return a->fail;
    *epoch = a->epoch;
    return 0;
}
"""

CASES = r"""
static void test_amp_pair(void)
{
    struct snd_soc_card card, foreign;
    int left_dev, right_dev;
    struct snd_soc_component left = {&card, "SpkrLeft", &left_dev};
    struct snd_soc_component right = {&card, "SpkrRight", &right_dev};
    struct snd_soc_component macro = {&card, NULL, NULL};
    struct snd_soc_dai codecs[] = {{&right}, {&macro}, {&left}};
    struct snd_soc_dai_link tx = {"WSA VI Protection"}, rx = {"WSA Playback"};
    struct snd_soc_pcm_runtime runtimes[] = {{&tx, codecs, 3, &card}, {&rx, codecs, 3, &card}};
    struct q6apm_fullio_amp_pair pair;

    card = (struct snd_soc_card){.runtimes = runtimes, .nruntimes = 2};
#define CHECK(link, expected) do { \
    pair = (struct q6apm_fullio_amp_pair){0}; \
    assert(q6apm_fullio_amp_pair(&card, link, &pair) == (expected)); \
} while (0)
    CHECK("WSA Playback", 0);
    assert(pair.left == &left && pair.right == &right);
    CHECK("WSA VI Protection", 0);
    CHECK("WSA CPS Protection", -ENODEV);
    runtimes[0].dai_link = &rx;
    CHECK("WSA Playback", -EEXIST);
    runtimes[0].dai_link = &tx;
    codecs[2].component = &right;
    CHECK("WSA Playback", -EEXIST);
    codecs[2].component = &macro;
    CHECK("WSA Playback", -ENODEV);
    codecs[2].component = &left;
    left.card = &foreign;
    CHECK("WSA Playback", -ENODEV);
    left.card = &card;
    left.dev = NULL;
    CHECK("WSA Playback", -ENODEV);
    left.dev = right.dev;
    CHECK("WSA Playback", -EEXIST);
#undef CHECK
}

static void test_mute_lifetime(void)
{
    struct q6apm apm = {0};
    struct device parent = {.apm = &apm}, dev = {.parent = &parent};
    struct q6apm_graph graph = {.apm = &apm}, other = {.apm = &apm};
    struct q6apm_fullio_mute_ticket attempt, newer;

    assert(q6apm_fullio_mute_begin(&graph, &attempt) == -EAGAIN);
    q6apm_fullio_set_transport(&dev, Q6APM_FULLIO_VI, true);
    q6apm_fullio_set_transport(&dev, Q6APM_FULLIO_CPS, true);
    assert(q6apm_fullio_mute_begin(&graph, &attempt) == 0);
    assert(q6apm_fullio_mute_begin(&other, &newer) == 0);
    assert(q6apm_fullio_mute_commit(&other, &attempt) == -ESTALE);
    assert(q6apm_fullio_mute_commit(&graph, &attempt) == 0);
    assert(q6apm_fullio_mute_is_verified(&graph));
    assert(!q6apm_fullio_mute_is_verified(&other));
    q6apm_fullio_mute_invalidate(&graph);
    assert(!q6apm_fullio_mute_is_verified(&graph));
    assert(q6apm_fullio_mute_commit(&graph, &attempt) == -ESTALE);

    assert(q6apm_fullio_mute_begin(&graph, &attempt) == 0);
    q6apm_fullio_set_transport(&dev, Q6APM_FULLIO_CPS, false);
    q6apm_fullio_set_transport(&dev, Q6APM_FULLIO_CPS, true);
    assert(q6apm_fullio_mute_commit(&graph, &attempt) == -ESTALE);
    assert(q6apm_fullio_mute_begin(&graph, &newer) == 0);
    assert(q6apm_fullio_mute_commit(&graph, &newer) == 0);
    q6apm_fullio_set_transport(&dev, Q6APM_FULLIO_VI, false);
    q6apm_fullio_set_transport(&dev, Q6APM_FULLIO_VI, true);
    assert(!q6apm_fullio_mute_is_verified(&graph));

    graph.fullio_mute_epoch = U64_MAX - 1;
    assert(q6apm_fullio_mute_begin(&graph, &newer) == -EOVERFLOW);
}

static void test_ready(void)
{
    struct wsa884x_fullio_pa_snapshot sample = {.enable = 1, .sta0 = 0x2f};
    assert(wsa884x_fullio_check_ready(&sample) == 0);
    sample.enable = 0;
    assert(wsa884x_fullio_check_ready(&sample) == -EAGAIN);
    sample.enable = 1;
    sample.sta0 = 0x2a;
    assert(wsa884x_fullio_check_ready(&sample) == -EAGAIN);
    sample.sta0 = 0x2f;
    sample.sta1 = 6;
    assert(wsa884x_fullio_check_ready(&sample) == -EIO);
    sample.sta1 = 0;
    sample.err0 = 8;
    assert(wsa884x_fullio_check_ready(&sample) == -EIO);
    sample.err0 = 0;
    sample.err1 = 1;
    assert(wsa884x_fullio_check_ready(&sample) == -EIO);
}

static void test_post_pa(void)
{
    struct q6apm apm = {.fullio_transport = BIT(Q6APM_FULLIO_VI) | BIT(Q6APM_FULLIO_CPS)};
    struct q6apm_graph graph = {.apm = &apm};
    struct q6apm_fullio_mute_ticket ticket;
    struct q6apm_dai_rtd prtd = {&graph};
    struct snd_pcm_runtime pcm = {&prtd};
    bool marker = false;
    struct device card_dev = {.of_node = &marker};
    struct snd_soc_card card;
    struct fake_amp l = {0}, r = {0};
    struct snd_soc_component left = {&card, "SpkrLeft", &l};
    struct snd_soc_component right = {&card, "SpkrRight", &r};
    struct snd_soc_dai codecs[] = {{&left}, {&right}};
    struct snd_soc_dai_link link = {"WSA Playback"};
    struct snd_soc_pcm_runtime rtd = {&link, codecs, 2, &card};
    struct snd_pcm_substream substream = {&pcm, &rtd, SNDRV_PCM_STREAM_PLAYBACK};
    struct q6apm_fullio_pa_check check = {.substream = &substream};

    card = (struct snd_soc_card){&rtd, 1, &card_dev};
    assert(q6apm_fullio_mute_begin(&graph, &ticket) == 0);
    assert(q6apm_fullio_verify_post_pa(&check) == -EPERM);
    marker = true;
    assert(q6apm_fullio_verify_post_pa(&check) == -EPERM && pa_checks == 0);
    assert(q6apm_fullio_mute_commit(&graph, &ticket) == 0);
    l.fail = -EAGAIN;
    assert(q6apm_fullio_verify_post_pa(&check) == -EAGAIN && !check.sampled);
    l.fail = 0;
    r.fail = -EIO;
    assert(q6apm_fullio_verify_post_pa(&check) == -EIO && !check.sampled);
    r.fail = 0;
    pa_checks = 0;
    epoch_change_after = 3;
    assert(q6apm_fullio_verify_post_pa(&check) == -ESTALE && !check.sampled);
    epoch_change_after = 0;
    assert(q6apm_fullio_verify_post_pa(&check) == 0 && check.sampled);
    assert(q6apm_fullio_verify_post_pa(&check) == 0);
    r.epoch++;
    assert(q6apm_fullio_verify_post_pa(&check) == -ESTALE);
    q6apm_fullio_mute_invalidate(&graph);
    assert(q6apm_fullio_verify_post_pa(&check) == -EPERM);
}

int main(void)
{
    u8 packet[124] = {0}, out[104];
    struct gpr_resp_pkt rsp = {packet, sizeof(packet)};
    struct q6apm_fullio_get get = {0x4a63, 0x08001039, sizeof(out), out};
    const u32 request_words[] = {0, get.instance, get.param, 16, 0, 1, 6, 0, 1};

    for (unsigned int i = 0; i < sizeof(request_words) / sizeof(*request_words); i++)
        put_word(packet, i, request_words[i]);

    memset(out, 0xab, sizeof(out));
    memset(packet + 36, 0xde, sizeof(packet) - 36); /* Unused capacity. */
    assert(q6apm_fullio_readback(&rsp, &get) == 16);
    assert(audioreach_fullio_compact_stereo_mute(out));
    for (size_t i = 16; i < sizeof(out); i++)
        assert(out[i] == 0xab);

    /* Only a single explicitly muted FL+FR entry is acceptable. */
    const struct { unsigned int word; u32 value; } bad[] = {
        {5, 0}, {5, 2}, {6, 2}, {6, 4}, {6, 7}, {7, 1}, {8, 0}, {8, 2},
    };
    for (unsigned int i = 0; i < sizeof(bad) / sizeof(*bad); i++) {
        put_word(packet, bad[i].word, bad[i].value);
        assert(q6apm_fullio_readback(&rsp, &get) == 16);
        assert(!audioreach_fullio_compact_stereo_mute(out));
        put_word(packet, bad[i].word, request_words[bad[i].word]);
    }

    for (unsigned int i = 0; i < 5; i++) {
        put_word(packet, i, request_words[i] ^ 1);
        assert(q6apm_fullio_readback(&rsp, &get) == (i ? -EPROTO : -EIO));
        put_word(packet, i, request_words[i]);
    }
    for (int n = -1; n < (int)sizeof(packet); n++) {
        rsp.payload_size = n;
        assert(q6apm_fullio_readback(&rsp, &get) == -EPROTO);
    }
    rsp.payload_size = sizeof(packet) + 1;
    assert(q6apm_fullio_readback(&rsp, &get) == -EPROTO);
    rsp.payload_size = sizeof(packet);
    put_word(packet, 3, sizeof(out));
    assert(q6apm_fullio_readback(&rsp, &get) == 0);
    assert(!memcmp(out, packet + 20, sizeof(out)));

    /* SP and SPVI retain their exact, independent format checks. */
    const struct { u32 iid, param, bytes; int outer; } tags[] = {
        {0x4027, 0x080011e8, 68, 92}, {0x4024, 0x080011f6, 44, 68},
    };
    for (unsigned int i = 0; i < sizeof(tags) / sizeof(*tags); i++) {
        get.instance = tags[i].iid;
        get.param = tags[i].param;
        get.bytes = tags[i].bytes;
        rsp.payload_size = tags[i].outer;
        put_word(packet, 1, get.instance);
        put_word(packet, 2, get.param);
        put_word(packet, 3, 16);
        assert(q6apm_fullio_readback(&rsp, &get) == -EPROTO);
        put_word(packet, 3, get.bytes);
        assert(q6apm_fullio_readback(&rsp, &get) == 0);
    }
    test_amp_pair();
    test_mute_lifetime();
    test_ready();
    test_post_pa();
}
"""


def extract(file, begin, end):
    text = file.read_text()
    start = text.index(begin)
    return text[start:text.index(end, start)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_tree", type=Path, help="Surface-next tree with FullIO patches applied")
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    args = parser.parse_args()
    qdsp = args.kernel_tree / "sound/soc/qcom/qdsp6"
    readback = extract(qdsp / "q6apm.c", "static int q6apm_fullio_readback(",
                       "static bool q6apm_fullio_oob_reply(")
    mute = extract(qdsp / "audioreach.c", "static bool audioreach_fullio_compact_stereo_mute(",
                   "/* The pinned endpoint ABI")
    dai = qdsp / "q6apm-dai.c"
    amp_pair = extract(dai, "struct q6apm_fullio_amp_pair {",
                       "/* One synchronous clock transaction")
    post_pa = extract(dai, "struct q6apm_fullio_pa_check {",
                      "static int q6apm_fullio_both_pa_off(")
    ticket = extract(qdsp / "q6apm.h", "struct q6apm_fullio_mute_ticket {",
                     "void q6apm_fullio_mute_invalidate(")
    lifetime = extract(qdsp / "q6apm.c", "void q6apm_fullio_set_transport(",
                       "int q6apm_send_cmd_sync(")
    codec = qdsp.parent.parent / "codecs/wsa884x.c"
    snapshot = extract(codec, "struct wsa884x_fullio_pa_snapshot {", "/* Return a hardware snapshot")
    ready = extract(codec, "static int wsa884x_fullio_check_ready(", "int wsa884x_fullio_pa_ready(")
    with tempfile.TemporaryDirectory(prefix="fullio-mute-readback-") as tmp:
        source = Path(tmp) / "test.c"
        binary = Path(tmp) / "test"
        source.write_text(PREAMBLE + readback + mute + amp_pair + ticket + lifetime
                          + snapshot + ready + PA_CHECK_STUB + post_pa + CASES)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-sign-compare", str(source), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)
    print("FullIO: readback, graph-local mute, pairing and post-PA guard passed")


if __name__ == "__main__":
    main()
