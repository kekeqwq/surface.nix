#!/usr/bin/env python3
"""Exercise the real fault-audit worker/lifetime helpers with a modeled queue."""

import argparse
from pathlib import Path
import subprocess
import tempfile


STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>

#define SDW_SLAVE_ATTACHED 1
#define EXPORT_SYMBOL_GPL(x)
#define READ_ONCE(x) (x)
#define dev_info(...) ((void)0)
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define atomic_t int
#define ATOMIC_INIT(v) (v)
#define atomic_read(p) (*(p))
static int atomic_cmpxchg(int *p, int from, int to)
{
    int previous = *p;
    if (previous == from) *p = to;
    return previous;
}
#define spin_lock_irqsave(lock, flags) do { (flags) = 0; assert(!(*(lock))++); } while (0)
#define spin_unlock_irqrestore(lock, flags) do { assert(--*(lock) == 0 && !(flags)); } while (0)

struct work_struct { void (*fn)(struct work_struct *); bool queued; };
struct sdw_slave { int status; };
struct wsa884x_priv {
    struct work_struct *fullio_fault_work;
    struct sdw_slave *slave;
    int fullio_fault_lock;
};
struct snd_soc_component { struct wsa884x_priv *amp; };
struct snd_soc_card { struct snd_soc_component *left, *right; };
struct q6apm_fullio_amp_pair { struct snd_soc_component *left, *right; };
static struct wsa884x_priv amp[2];
static int dispatched, stops, stop_error;
static bool drop_notice;

#define INIT_WORK_ONSTACK(w, cb) (*(w) = (struct work_struct){ .fn = (cb) })
static void schedule_work(struct work_struct *w) { w->queued = !drop_notice; }
static void flush_work(struct work_struct *w)
{
    assert(amp[0].fullio_fault_work != w && amp[1].fullio_fault_work != w);
    if (w->queued) {
        w->queued = false;
        dispatched++;
        w->fn(w);
        w->fn(w); /* account for a duplicate notice racing execution */
    }
}
static void destroy_work_on_stack(struct work_struct *w) { assert(!w->queued); }
static struct wsa884x_priv *wsa884x_fullio_fault_audit_amp(struct snd_soc_component *c)
{
    return c ? c->amp : NULL;
}
static int q6apm_fullio_amp_pair(struct snd_soc_card *c, const char *link,
                               struct q6apm_fullio_amp_pair *pair)
{
    assert(link && c->left != c->right);
    *pair = (struct q6apm_fullio_amp_pair){c->left, c->right};
    return 0;
}
static int q6apm_fullio_stop_pair_audit(struct snd_soc_card *c)
{
    assert(c && !amp[0].fullio_fault_lock && !amp[1].fullio_fault_lock);
    stops++;
    return stop_error;
}
"""

CHECKS = r"""
int main(void)
{
    struct sdw_slave slaves[2] = {{SDW_SLAVE_ATTACHED}, {SDW_SLAVE_ATTACHED}};
    struct snd_soc_component left = {&amp[0]}, right = {&amp[1]};
    struct snd_soc_card card = {&left, &right};
    struct work_struct unrelated = {0};
    bool verified = false;
    amp[0].slave = &slaves[0];
    amp[1].slave = &slaves[1];
    assert(!wsa884x_fullio_queue_fault(&amp[0]));
    assert(wsa884x_fullio_fault_inject(&left) == -EOPNOTSUPP);

    assert(q6apm_fullio_fault_worker_audit(&card, &verified) == -ECANCELED && verified);
    assert(dispatched == 1 && stops == 1);
    assert(!amp[0].fullio_fault_work && !amp[1].fullio_fault_work);

    verified = false;
    slaves[1].status = 0;
    assert(q6apm_fullio_fault_worker_audit(&card, &verified) == -ENODEV && !verified);
    assert(!amp[0].fullio_fault_work && !amp[1].fullio_fault_work && stops == 1);
    slaves[1].status = SDW_SLAVE_ATTACHED;
    assert(!wsa884x_fullio_fault_watch(&right, &unrelated, true));
    assert(q6apm_fullio_fault_worker_audit(&card, &verified) == -EBUSY && !verified);
    assert(!amp[0].fullio_fault_work && amp[1].fullio_fault_work == &unrelated);
    assert(!wsa884x_fullio_fault_watch(&right, &unrelated, false));

    drop_notice = true;
    assert(q6apm_fullio_fault_worker_audit(&card, &verified) == -ENODATA && !verified);
    assert(dispatched == 1 && stops == 1);
    drop_notice = false;
    stop_error = -EIO;
    assert(q6apm_fullio_fault_worker_audit(&card, &verified) == -EIO && !verified);
    assert(!amp[0].fullio_fault_work && !amp[1].fullio_fault_work);
    assert(dispatched == 2 && stops == 2);
}
"""


def extract(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_tree", type=Path)
    args = parser.parse_args()
    soc = args.kernel_tree / "sound/soc"
    codec = (soc / "codecs/wsa884x.c").read_text()
    dai = (soc / "qcom/qdsp6/q6apm-dai.c").read_text()
    queue = extract(codec, "static bool wsa884x_fullio_queue_fault(", "static int wsa884x_update_status(")
    watch = extract(codec, "int wsa884x_fullio_fault_watch(", "EXPORT_SYMBOL_GPL(wsa884x_fullio_fault_inject)")
    worker = extract(dai, "struct q6apm_fullio_fault_work {", "static int q6apm_fullio_verify_sink(")
    with tempfile.TemporaryDirectory(prefix="fullio-notice-") as tmp:
        source, binary = Path(tmp) / "worker.c", Path(tmp) / "worker"
        source.write_text(STUBS + queue + watch + worker + CHECKS)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", source, "-o", binary], check=True)
        subprocess.run([binary], check=True)
    print("FullIO fault worker: scoped arm, duplicate notice, disarm-before-join and failures passed")


if __name__ == "__main__":
    main()
