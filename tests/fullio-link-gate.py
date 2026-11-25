#!/usr/bin/env python3
"""Exercise the extracted SoundWire new-stream lockout and PM vote balance."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#define READ_ONCE(v) (v)
#define cmpxchg(p, o, n) exchange((p), (o), (n))
#define dev_err(...) ((void)0)
#define dev_err_ratelimited(...) ((void)0)
struct qcom_swrm_ctrl;
struct device { struct qcom_swrm_ctrl *ctrl; };
struct snd_pcm_substream { int stream; };
struct snd_soc_dai { struct device *dev; };
struct qcom_swrm_ctrl { struct device *dev; bool fullio_link_gate; int fullio_link_error; };
static int pm_refs, pm_calls, runtime_error, fault_during_resume;
static int exchange(int *ptr, int old, int next)
{
    int previous = *ptr;
    if (previous == old) *ptr = next;
    return previous;
}
static struct qcom_swrm_ctrl *dev_get_drvdata(struct device *dev) { return dev->ctrl; }
static void qcom_swrm_fullio_latch_link_error(struct qcom_swrm_ctrl *ctrl, int error);
static int pm_runtime_get_sync(struct device *dev)
{
    pm_refs++;
    pm_calls++;
    if (fault_during_resume) qcom_swrm_fullio_latch_link_error(dev->ctrl, fault_during_resume);
    return runtime_error;
}
static void pm_runtime_put_noidle(struct device *dev) { assert(dev && --pm_refs >= 0); }
static void pm_runtime_put_autosuspend(struct device *dev) { pm_runtime_put_noidle(dev); }
"""

CHECKS = r"""
int main(void)
{
    struct qcom_swrm_ctrl ctrl = {0}, other = {0};
    struct device dev = {&ctrl};
    struct snd_soc_dai dai = {&dev};
    struct snd_pcm_substream stream = {0};
    ctrl.dev = &dev;

    /* An unmarked controller is not part of the experiment. */
    qcom_swrm_fullio_latch_link_error(&ctrl, -EIO);
    assert(!qcom_swrm_startup(&stream, &dai) && pm_calls == 1 && pm_refs == 1);
    pm_runtime_put_noidle(&dev);

    ctrl.fullio_link_gate = true;
    runtime_error = -ETIMEDOUT;
    assert(qcom_swrm_startup(&stream, &dai) == -ETIMEDOUT && pm_calls == 2 && !pm_refs);
    runtime_error = 0;
    fault_during_resume = -EIO;
    assert(qcom_swrm_startup(&stream, &dai) == -ENOTRECOVERABLE && pm_calls == 3 && !pm_refs);
    assert(ctrl.fullio_link_error == -EIO);
    qcom_swrm_fullio_latch_link_error(&ctrl, 0);
    qcom_swrm_fullio_latch_link_error(&ctrl, -EPROTO);
    assert(ctrl.fullio_link_error == -EIO);
    fault_during_resume = 0;
    assert(qcom_swrm_startup(&stream, &dai) == -ENOTRECOVERABLE && pm_calls == 3 && !pm_refs);
    assert(!qcom_swrm_fullio_new_stream_ok(&other));

    /* The stock -EACCES path owns a PM ref too; balance it if latched. */
    ctrl.fullio_link_error = 0; /* independent fixture, not a recovery path */
    runtime_error = -EACCES;
    fault_during_resume = -EIO;
    assert(qcom_swrm_startup(&stream, &dai) == -ENOTRECOVERABLE && pm_calls == 4 && !pm_refs);
}
"""


def function(text, name):
    match = re.search(rf"^static (?:int|void) {name}\([^{{]*\{{.*?^\}}", text, re.M | re.S)
    if match is None:
        raise ValueError(f"missing {name}")
    return match.group()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path, help="patched drivers/soundwire/qcom.c")
    text = p.parse_args().source.read_text()
    setup = function(text, "qcom_swrm_hw_params")
    assert setup.index("qcom_swrm_fullio_new_stream_ok(") < setup.index("qcom_swrm_denali_alloc_feedback(")
    parts = [function(text, n) for n in ("qcom_swrm_fullio_latch_link_error", "qcom_swrm_fullio_new_stream_ok", "qcom_swrm_startup")]
    with tempfile.TemporaryDirectory() as work:
        source = Path(work) / "latch.c"
        binary = source.with_suffix("")
        source.write_text(STUBS + "\n".join(parts) + CHECKS)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", source, "-o", binary], check=True)
        subprocess.run([binary], check=True)
    print("SoundWire link gate: sticky first fault, new stream denied, PM references balanced, unrelated controller unchanged.")


if __name__ == "__main__":
    main()
