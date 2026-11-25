packages:
{
  dspPrepare ? false,
  dspStart ? false,
  sidechain ? false,
  immediateTaps ? false,
  stopFault ? false,
  holdAtDiscovery ? false,
  gainAudit ? false,
  paStopAudit ? false,
  faultWorker ? false,
  codecGuardAudit ? false,
  missingStopProof ? false,
  linkGateTest ? false,
  vphxAudit ? false,
  sinkReadback ? false,
  softCycle ? false,
  frameStopAudit ? false,
  rx0TagAudit ? false,
  rx0LogOff ? false,
  feedbackLogOff ? false,
  keepCpsLog ? false,
  ringMapAudit ? false,
  ringAttachAudit ? false,
  ringDmaAudit ? false,
  sinkBankAudit ? false,
}:
{ lib, pkgs, ... }:
let
  dtb = "qcom/x1e80100-microsoft-denali-oled.dtb";
  loggerFixture = if keepCpsLog then "cps-only-log" else if feedbackLogOff then "1586-log-off" else if rx0LogOff then "rx0-log-off" else "rx0-tag";
  taggedTopology = pkgs.runCommand "denali-fullio-${loggerFixture}-audit-topology" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out/share/sp11-fullio"
    python3 ${../../tests/fullio-topology.py} \
      ${packages.fullio-reference-topology}/share/sp11-fullio/v19c.bin \
      --retag-rx0-out "$out/share/sp11-fullio/v19c.bin" \
      ${lib.optionalString rx0LogOff "--rx0-log-off"} ${lib.optionalString feedbackLogOff "--feedback-log-off"} ${lib.optionalString keepCpsLog "--keep-cps-log"}
  '';
  fixturePackages = packages // lib.optionalAttrs rx0TagAudit {
    fullio-reference-topology = taggedTopology;
  };
  auditedDtbs =
    pkgs.runCommand "denali-fullio-clock-off-audit-dtbs" {
      nativeBuildInputs = [ pkgs.dtc pkgs.python3 ];
    }
      ''
          install -Dm644 ${packages.fullio-muted-kernel}/dtbs/${dtb} "$out/${dtb}"
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-clock-off-audit
        ${lib.optionalString dspPrepare ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-dsp-prepare-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-dsp-prepare-audit
        ''}
        ${lib.optionalString (ringDmaAudit && holdAtDiscovery) ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-ring-dma-held-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-ring-dma-held-audit
        ''}
        ${lib.optionalString ringDmaAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-ring-dma-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-ring-dma-audit
        ''}
        ${lib.optionalString ringAttachAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-ring-attach-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-ring-attach-audit
        ''}
        ${lib.optionalString ringMapAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-ring-map-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-ring-map-audit
        ''}
        ${lib.optionalString softCycle ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-soft-cycle-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-soft-cycle-audit
        ''}
        ${lib.optionalString sinkReadback ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-sink-readback-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-sink-readback-audit
        ''}
        ${lib.optionalString vphxAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-vphx-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-vphx-audit
        ''}
        ${lib.optionalString sinkBankAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-sink-bank-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-sink-bank-audit
        ''}
        ${lib.optionalString dspStart ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-dsp-start-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-dsp-start-audit
        ''}
        ${lib.optionalString sidechain ''
          swr=/soc@0/soundwire@6b10000
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-feedback
          fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-sidechain-audit
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-sidechain-audit
          if fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-feedback-capture-test 2>/dev/null; then
            echo 'Integrated sidechain audit cannot use a capture-only controller.' >&2
            exit 1
          fi
        ''}
        ${lib.optionalString immediateTaps ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-immediate-taps-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-immediate-taps-audit
        ''}
        ${lib.optionalString stopFault ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-dsp-stop-fault-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-dsp-stop-fault-audit
        ''}
        ${lib.optionalString gainAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-gain-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-gain-audit
        ''}
        ${lib.optionalString paStopAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-pa-stop-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-pa-stop-audit
        ''}
        ${lib.optionalString faultWorker ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-fault-worker
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-fault-worker
        ''}
        ${lib.optionalString codecGuardAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-guard-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-guard-audit
        ''}
        ${lib.optionalString missingStopProof ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-missing-stop-proof
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-pa-off-missing-stop-proof
        ''}
        ${lib.optionalString (linkGateTest || ringDmaAudit) ''
          swr=/soc@0/soundwire@6b10000
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-feedback
          fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate
        ''}
        ${lib.optionalString rx0TagAudit ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-rx0-tag-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-rx0-tag-audit
        ''}
        ${lib.optionalString rx0LogOff ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-rx0-log-off-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-rx0-log-off-audit
        ''}
        ${lib.optionalString feedbackLogOff ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-feedback-log-off-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-feedback-log-off-audit
        ''}
        ${lib.optionalString keepCpsLog ''
          fdtput "$out/${dtb}" /sound microsoft,denali-fullio-keep-cps-log-audit
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-keep-cps-log-audit
        ''}
        ${lib.optionalString frameStopAudit ''
          fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-wait-frame-stop
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-wait-frame-stop
        ''}
        ${lib.optionalString linkGateTest ''
          fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate-test
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate-test
        ''}
        ${lib.optionalString ringDmaAudit ''
          fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-pm-transition-audit
          fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-pm-transition-audit
          if fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate-test 2>/dev/null; then
            echo 'Ring DMA audit requires the real link latch, not the seeded failure.' >&2
            exit 1
          fi
        ''}
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-muted-test
          fdtget "$out/${dtb}" /sound microsoft,denali-fullio-clock-off-audit
          python3 ${../../tests/fullio-render-dtb.py} "$out/${dtb}"
          if fdtget "$out/${dtb}" /sound microsoft,denali-fullio-post-pa-test 2>/dev/null; then
            echo 'Clock-off audit must not permit a post-PA transaction.' >&2
            exit 1
          fi
      '';
in
assert !dspStart || dspPrepare;
assert !sidechain || dspStart;
assert !immediateTaps || sidechain;
assert !stopFault || (sidechain && !immediateTaps);
assert !holdAtDiscovery || ((sidechain || sinkReadback) && !stopFault);
assert !sinkReadback || (ringAttachAudit && vphxAudit && holdAtDiscovery && !dspStart);
assert !softCycle || (ringDmaAudit && immediateTaps && holdAtDiscovery && !stopFault);
assert !frameStopAudit || (ringDmaAudit && !holdAtDiscovery && !stopFault);
assert !rx0TagAudit || (frameStopAudit && immediateTaps && !softCycle);
assert !rx0LogOff || rx0TagAudit;
assert !feedbackLogOff || rx0LogOff;
assert !keepCpsLog || feedbackLogOff;
# The kernel patch stack contains the sticky shutdown-proof render latch for
# every fixture; missingStopProof only injects a diagnostic failure.
assert !gainAudit || holdAtDiscovery;
assert !paStopAudit || gainAudit;
assert !faultWorker || (paStopAudit && !immediateTaps);
assert !codecGuardAudit || faultWorker;
assert !missingStopProof || (faultWorker && !codecGuardAudit);
assert !linkGateTest || (!dspPrepare && !sidechain);
assert !vphxAudit || (dspPrepare && !dspStart && !linkGateTest);
assert !ringMapAudit || ((vphxAudit || ringDmaAudit) && !sinkBankAudit && (!sidechain || ringDmaAudit));
assert !ringAttachAudit || ringMapAudit;
assert !ringDmaAudit || (ringAttachAudit && dspStart && !stopFault && !faultWorker);
assert !sinkBankAudit || vphxAudit;
{
  imports = [ (import ./fullio-muted.nix fixturePackages) ];
  hardware.deviceTree.dtbSource = auditedDtbs;
  # Test whether the first runtime clock-stop transition causes detach.
  # Only this one-shot fixture changes runtime-PM policy; PAs stay blocked.
  services.udev.extraRules = lib.mkIf holdAtDiscovery ''
    ACTION=="add|bind", SUBSYSTEM=="platform", KERNEL=="6b00000.codec", TEST=="power/control", ATTR{power/control}="on"
    ACTION=="add|bind", SUBSYSTEM=="platform", KERNEL=="6b10000.soundwire", TEST=="power/control", ATTR{power/control}="on"
  '';
  # Do not race raw ALSA diagnostics with WirePlumber's startup PCM probes.
  services.pipewire.wireplumber.extraConfig."99-fullio-sidechain-probe" = lib.mkIf (sidechain || linkGateTest || vphxAudit || ringDmaAudit) {
    "monitor.alsa.rules" = [
      {
        matches = [ { "device.name" = "alsa_card.platform-sound"; } ];
        actions.update-props."device.disabled" = true;
      }
    ];
  };
}
