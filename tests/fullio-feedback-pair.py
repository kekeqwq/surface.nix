#!/usr/bin/env python3
"""Exercise the patched feedback-source admission check without a SoundWire bus."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
helper = re.search(r'^static int qcom_swrm_denali_feedback_source\([^\{]+\{.*?^\}',
                   text, re.M | re.S).group()
alloc = text[text.index('static int qcom_swrm_denali_alloc_feedback('):]
assert alloc.index('qcom_swrm_denali_feedback_source(') < alloc.index('sdw_stream_add_master(')
source = r'''
#include <assert.h>
#include <errno.h>
#define READ_ONCE(x) (x)
#define BIT(n) (1UL << (n))
#define SDW_MAX_DEVICES 11
#define SDW_SLAVE_ATTACHED 1
struct sdw_bus { int id; };
struct sdw_slave {
    struct sdw_bus *bus;
    struct { unsigned short part_id; } id;
    unsigned short dev_num;
    int status;
};
''' + helper + r'''
int main(void)
{
    struct sdw_bus bus = {0}, other = {1};
    struct sdw_slave left = { &bus, {0x0204}, 2, SDW_SLAVE_ATTACHED };
    struct sdw_slave right = { &bus, {0x0204}, 1, SDW_SLAVE_ATTACHED };
    struct sdw_slave fake = left;
    unsigned long seen = 0;
    assert(!qcom_swrm_denali_feedback_source(&bus, &left, &seen));
    assert(qcom_swrm_denali_feedback_source(&bus, &left, &seen) == -EINVAL);
    assert(qcom_swrm_denali_feedback_source(&bus, &fake, &seen) == -EINVAL);
    fake.bus = &other;
    fake.dev_num = 4;
    assert(qcom_swrm_denali_feedback_source(&bus, &fake, &seen) == -EINVAL);
    fake.bus = &bus;
    fake.id.part_id = 0x0217;
    assert(qcom_swrm_denali_feedback_source(&bus, &fake, &seen) == -EINVAL);
    fake.id.part_id = 0x0204;
    fake.status = 0;
    assert(qcom_swrm_denali_feedback_source(&bus, &fake, &seen) == -ENODEV);
    fake.status = SDW_SLAVE_ATTACHED;
    fake.dev_num = 0;
    assert(qcom_swrm_denali_feedback_source(&bus, &fake, &seen) == -ENODEV);
    fake.dev_num = SDW_MAX_DEVICES + 1;
    assert(qcom_swrm_denali_feedback_source(&bus, &fake, &seen) == -ENODEV);
    assert(seen == BIT(2));
    assert(!qcom_swrm_denali_feedback_source(&bus, &right, &seen));
    assert(seen == (BIT(1) | BIT(2)));
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 'pair.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Feedback admission: only two distinct attached WSA codec slots accepted; bad slots leave the pair unchanged.')
