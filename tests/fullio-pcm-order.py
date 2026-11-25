#!/usr/bin/env python3
"""Model future FullIO PCM lock/lifetime constraints; not a driver or hardware test."""
import argparse
from dataclasses import dataclass
from pathlib import Path
import re


def body(text, name):
    return re.search(rf'^\w[^\n]*\b{name}\([^{{;]*\n\{{.*?^\}}', text, re.M | re.S)[0]


def source_contract(alsa, apr, soc, dai, apm):
    assert 'guard(pcm_stream_lock_irq)(substream)' in body(alsa, 'snd_pcm_action_lock_irq')
    assert 'snd_pcm_action_group(ops, substream, state, true)' in body(alsa, 'snd_pcm_action')
    group = body(alsa, 'snd_pcm_action_group')
    assert group.index('mutex_lock_nested(&s->self_group.mutex') < group.index('ops->do_action')
    assert group.index('spin_lock_nested(&s->self_group.lock') < group.index('ops->do_action')
    ordered = ('ops->do_action(s, state)', 'ops->undo_action(s1, state)',
               'ops->post_action(s, state)')
    unlock = re.search(r'mutex_unlock\(&s1?->self_group\.mutex\)', group)
    positions = [group.index(anchor) for anchor in ordered] + [unlock.start()]
    assert positions == sorted(positions)
    nonatomic = body(alsa, 'snd_pcm_action_nonatomic')
    assert nonatomic.index('snd_pcm_buffer_access_lock') < nonatomic.index('snd_pcm_action_single') < \
        nonatomic.index('snd_pcm_buffer_access_unlock')
    assert 'snd_pcm_action_group(ops, substream, state, false)' in nonatomic
    assert group.index('__snd_pcm_buffer_access_lock') < positions[0] < group.index('snd_pcm_buffer_access_unlock')
    assert 'if (s1 == s) /* failed stream */' in group
    assert 'SNDRV_PCM_TRIGGER_STOP' in body(alsa, 'snd_pcm_undo_start')
    assert 'SNDRV_PCM_TRIGGER_PAUSE_RELEASE' in body(alsa, 'snd_pcm_undo_pause')
    assert 'SNDRV_PCM_TRIGGER_PAUSE_PUSH' in body(alsa, 'snd_pcm_undo_pause')
    stop = body(alsa, 'snd_pcm_do_stop')
    assert re.search(r'^\s+substream->ops->trigger\(substream, SNDRV_PCM_TRIGGER_STOP\);$', stop, re.M)
    sync = body(alsa, 'snd_pcm_sync_stop')
    assert re.search(r'^\s+substream->ops->sync_stop\(substream\);$', sync, re.M)
    xrun = body(alsa, 'snd_pcm_stop_xrun')
    assert 'guard(pcm_stream_lock_irqsave)(substream)' in xrun
    assert xrun.index('snd_pcm_running(substream)') < xrun.index('__snd_pcm_xrun(substream)')
    fe = body(soc, 'dpcm_fe_dai_trigger')
    assert fe.index('trigger_pending = cmd + 1') < fe.index('return 0;') < fe.index('return dpcm_fe_dai_do_trigger')
    apply_pending = body(soc, 'dpcm_set_fe_update_state')
    assert apply_pending.index('snd_pcm_stream_lock_irq') < apply_pending.index('dpcm_fe_dai_do_trigger(substream,') < \
        apply_pending.index('snd_pcm_stream_unlock_irq')
    complete = body(soc, 'dpcm_fe_dai_do_trigger')
    assert complete.index('if (ret < 0)\n\t\tgoto out;') < complete.index('state = SND_SOC_DPCM_STATE_START')
    assert 'create_singlethread_workqueue("qcom_apr_rx")' in apr
    assert body(apr, 'gpr_free_port').index('idr_remove') < body(apr, 'gpr_free_port').index('flush_workqueue')
    assert re.search(r'case APM_CLIENT_EVENT_DATA_READ_DONE:\s*snd_pcm_period_elapsed\(substream\);',
                     body(dai, 'event_handler'))
    assert 'independent && !prtd->fullio_reference_pcm ? NULL : event_handler' in dai
    assert re.search(r'case APM_CLIENT_EVENT_WATERMARK_EVENT:\s*q6apm_pcm_watermark_queue\(prtd\);',
                     body(dai, 'event_handler'))
    queue = body(dai, 'q6apm_pcm_watermark_queue')
    assert queue.index('!prtd->watermark_enabled') < queue.index('schedule_work')
    assert 'snd_pcm_' not in queue
    notify = body(dai, 'q6apm_pcm_watermark_work')
    assert (notify.index('snd_pcm_stream_lock_irqsave') < notify.index('prtd->watermark_pending = false')
            < notify.index('snd_pcm_period_elapsed_under_stream_lock')
            < notify.index('snd_pcm_stream_unlock_irqrestore'))
    assert 'prtd->watermark_enabled && prtd->watermark_pending' in notify
    trigger = body(dai, 'q6apm_dai_trigger')
    for command, enabled in (('START', 'true'), ('STOP', 'false'), ('PAUSE_PUSH', 'false'),
                             ('PAUSE_RELEASE', 'true'), ('SUSPEND', 'false'), ('RESUME', 'true')):
        handlers = trigger.split('case SNDRV_PCM_TRIGGER_' + command + ':', 1)[1].split('break;', 1)[0]
        assert f'q6apm_pcm_watermark_enable(prtd, {enabled});' in handlers
        assert 'cancel_work' not in handlers
    close = body(dai, 'q6apm_dai_close')
    assert (close.index('q6apm_pcm_watermark_enable(prtd, false)') < close.index('cancel_work_sync')
            < close.index('q6apm_graph_close') < close.index('kfree(prtd)'))
    assert 'gpr_alloc_port(apm->gdev, dev, graph_callback, graph)' in body(apm, 'q6apm_graph_open')
    close = body(apm, 'q6apm_graph_close')
    assert (close.index('gpr_free_port(graph->port)') < close.index('graph->ar_graph = NULL')
            < close.index('q6apm_release_audioreach_graph(ar_graph)') < close.index('kfree(graph)'))


def cycle(deps):
    def visit(node, stack):
        if node in stack:
            return stack[stack.index(node):] + (node,)
        for dep in deps.get(node, ()):
            found = visit(dep, stack + (node,))
            if found:
                return found
        return ()
    return next((path for node in deps if (path := visit(node, ()))), ())


def lock_contract():
    # A linked capture callback may precede the control ACK on APR RX,
    # even when the render graph never calls period_elapsed on RX.
    deps = {'render trigger': ('APR RX',), 'APR RX': ('capture lock',),
            'capture lock': ('render trigger',)}
    assert cycle(deps) == ('render trigger', 'APR RX', 'capture lock', 'render trigger')
    assert not cycle({**deps, 'render trigger': ()})  # publish-only trigger
    # Do not drain a notifier that may be waiting for the lock you hold.
    deps = {'render trigger': ('notify worker',), 'notify worker': ('render lock',),
            'render lock': ('render trigger',)}
    assert cycle(deps)
    assert not cycle({**deps, 'render trigger': (), 'unlocked teardown': ('notify worker', 'APR RX')})


@dataclass(frozen=True)
class State:
    published: bool = False
    revoked: bool = False
    port_drained: bool = False
    notify_drained: bool = False
    freed: bool = False


def lifecycle(revoke=True, drain_port=True):
    # All interleavings of a racing APR callback, STOP, and unlocked teardown.
    # Callback publication and revocation serialize; the worker rechecks the
    # epoch under the PCM lock before calling ALSA, not when work is queued.
    seen = set()

    def walk(s):
        if s in seen:
            return
        seen.add(s)
        if s.freed:
            assert s.port_drained and s.notify_drained and not s.published
            return
        asdict = vars(s)

        def change(**kw):
            walk(State(**(asdict | kw)))

        if not s.port_drained and not s.published and not (s.revoked and revoke):
            change(published=True, notify_drained=False)
        if not s.revoked:
            change(revoked=True)
        if s.published:
            # A notifier dequeued after STOP must drop the revoked ticket.
            assert not (s.revoked and not revoke), 'late ALSA callback after STOP'
            change(published=False)
        if s.revoked and not s.port_drained:
            change(port_drained=True)
        if s.revoked and (s.port_drained or not drain_port) and not s.notify_drained:
            change(published=False, notify_drained=True)
        if s.notify_drained:
            change(freed=True)

    walk(State())
    assert any(s.freed for s in seen)


@dataclass(frozen=True)
class Start:
    # ALSA owns the group decision; an independent worker owns what may have
    # reached the DSP. STOP publication supersedes START but cannot unsend it.
    group: str = 'locked'
    dpcm: str = 'pending'
    wanted: bool = True
    dsp: str = 'none'
    poisoned: bool = False


def start_rollback(commit_barrier=True, dpcm_barrier=True, compensate=True):
    seen = set()

    def walk(s):
        if s in seen:
            return
        seen.add(s)
        if s.group != 'committed':
            assert s.dsp == 'none', 'START escaped before linked ALSA group commit'
        if s.dpcm != 'started':
            assert s.dsp == 'none', 'START escaped without completed DPCM trigger'
        if not s.wanted and s.dsp == 'acked':
            raise AssertionError('late START acknowledgement bypassed compensating teardown')

        def change(**kw):
            walk(Start(**(vars(s) | kw)))

        if s.group == 'locked':
            change(group='committed')
            # A peer failed; ALSA rolls back earlier successful trigger calls,
            # and the stream that failed is not in the undo range.
            change(group='rolled-back', wanted=False)
        if s.dpcm == 'pending' and s.group != 'rolled-back':
            change(dpcm='started')
            # A deferred DPCM operation can already have returned 0 to ALSA,
            # but a failed BE trigger leaves DPCM without START state.
            change(dpcm='failed')
        if s.group == 'committed' and s.wanted:
            pending = 'cleanup' if s.dsp == 'acked' else s.dsp
            change(wanted=False, dsp=pending)
        if (s.wanted and s.dsp == 'none'
                and (s.group == 'committed' or not commit_barrier)
                and (s.dpcm == 'started' or not dpcm_barrier)):
            change(dsp='sent')
        if s.dsp == 'sent':
            change(dsp='acked' if s.wanted or not compensate else 'cleanup')
            # Timeout/epoch loss means START may have reached firmware. Never
            # republish START on this graph; keep it owned until proof/retire.
            change(wanted=False, dsp='cleanup', poisoned=True)
        if s.dsp == 'cleanup':
            change(dsp='proved-off')
            change(dsp='unknown', poisoned=True)
        if s.dsp == 'unknown':
            assert s.poisoned and not s.wanted

    walk(Start())
    assert any(s.dsp == 'proved-off' for s in seen)
    assert any(s.dsp == 'unknown' for s in seen)


def admission():
    # This is cold reopen after retiring a graph, not a proposal to require
    # CLOSE and UNMAP for a future native, in-place SOFT_PAUSE transition.
    def can_reopen(*, dsp_stop, clock_off, both_pa_off, graph_close, both_unmaps):
        return all((dsp_stop, clock_off, both_pa_off, graph_close, both_unmaps))

    proof = dict(dsp_stop=True, clock_off=True, both_pa_off=True, graph_close=True, both_unmaps=True)
    assert can_reopen(**proof)
    for missing in proof:
        # ALSA reaching SETUP after a failed STOP never adds hardware evidence.
        assert not can_reopen(**(proof | {missing: False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcm_native', type=Path)
    parser.add_argument('apr', type=Path)
    parser.add_argument('soc_pcm', type=Path)
    parser.add_argument('q6apm_dai', type=Path)
    parser.add_argument('q6apm', type=Path)
    args = parser.parse_args()
    sources = (args.pcm_native, args.apr, args.soc_pcm, args.q6apm_dai, args.q6apm)
    source_contract(*(p.read_text() for p in sources))
    lock_contract()
    lifecycle()
    for mutation in ({'revoke': False}, {'drain_port': False}):
        try:
            lifecycle(**mutation)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'accepted unsafe lifetime mutation: {mutation}')
    start_rollback()
    for mutation in ({'commit_barrier': False}, {'dpcm_barrier': False}, {'compensate': False}):
        try:
            start_rollback(**mutation)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'accepted unsafe START rollback mutation: {mutation}')
    admission()
    print('PCM ordering: ALSA/DPCM commit barriers, late-ACK teardown, unlocked drain, and sticky shutdown proof required.')


if __name__ == '__main__':
    main()
