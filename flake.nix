{
  description = "Opt-in NixOS hardware support for Surface Pro 11 Denali OLED";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable-small";

  outputs =
    { nixpkgs, ... }:
    let
      system = "aarch64-linux";
      overlay = import ./overlay.nix;
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ overlay ];
      };
      kernel = pkgs.surfacePackages.surfaceNext;
      ringDmaTapsAudit = packages: { holdAtDiscovery, softCycle ? false, frameStopAudit ? false, rx0TagAudit ? false, rx0LogOff ? false, feedbackLogOff ? false, keepCpsLog ? false }:
        import ./modules/denali/fullio-clock-off-audit.nix packages {
          inherit holdAtDiscovery softCycle frameStopAudit rx0TagAudit rx0LogOff feedbackLogOff keepCpsLog;
          dspPrepare = true;
          dspStart = true;
          ringMapAudit = true;
          ringAttachAudit = true;
          ringDmaAudit = true;
          sidechain = true;
          immediateTaps = true;
        };
    in
    rec {
      overlays.default = overlay;
      nixosModules.default = ./modules/denali.nix;
      nixosModules.fullio-muted = import ./modules/denali/fullio-muted.nix packages.${system};
      nixosModules.fullio-reference-render =
        import ./modules/denali/fullio-reference-render.nix packages.${system};
      nixosModules.fullio-mic-desktop = import ./modules/denali/fullio-mic-desktop.nix packages.${system} { };
      nixosModules.fullio-pm-transition-audit =
        import ./modules/denali/fullio-mic-desktop.nix packages.${system} { pmTransitionAudit = true; };
      nixosModules.fullio-passive-link-audit =
        import ./modules/denali/fullio-mic-desktop.nix packages.${system} { passiveLinkAudit = true; };
      nixosModules.fullio-frame-stop-audit =
        import ./modules/denali/fullio-mic-desktop.nix packages.${system} {
          passiveLinkAudit = true;
          frameStopAudit = true;
        };
      nixosModules.fullio-clock-off-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { };
      nixosModules.fullio-link-gate-test =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { linkGateTest = true; };
      nixosModules.fullio-dsp-prepare-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; };
      nixosModules.fullio-ring-dma-taps-audit = ringDmaTapsAudit packages.${system} { holdAtDiscovery = false; };
      nixosModules.fullio-ring-dma-taps-held-audit = ringDmaTapsAudit packages.${system} { holdAtDiscovery = true; };
      nixosModules.fullio-frame-stop-render-audit = ringDmaTapsAudit packages.${system} {
        holdAtDiscovery = false;
        frameStopAudit = true;
      };
      nixosModules.fullio-rx0-tag-audit = ringDmaTapsAudit packages.${system} {
        holdAtDiscovery = false;
        frameStopAudit = true;
        rx0TagAudit = true;
      };
      nixosModules.fullio-rx0-log-off-audit = ringDmaTapsAudit packages.${system} {
        holdAtDiscovery = false;
        frameStopAudit = true;
        rx0TagAudit = true;
        rx0LogOff = true;
      };
      nixosModules.fullio-1586-log-off-audit = ringDmaTapsAudit packages.${system} {
        holdAtDiscovery = false;
        frameStopAudit = true;
        rx0TagAudit = true;
        rx0LogOff = true;
        feedbackLogOff = true;
      };
      nixosModules.fullio-cps-only-log-audit = ringDmaTapsAudit packages.${system} {
        holdAtDiscovery = false;
        frameStopAudit = true;
        rx0TagAudit = true;
        rx0LogOff = true;
        feedbackLogOff = true;
        keepCpsLog = true;
      };
      nixosModules.fullio-soft-cycle-audit = ringDmaTapsAudit packages.${system} {
        holdAtDiscovery = true;
        softCycle = true;
      };
      nixosModules.fullio-ring-dma-sidechain-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; dspStart = true; ringMapAudit = true; ringAttachAudit = true; ringDmaAudit = true; sidechain = true; };
      nixosModules.fullio-ring-dma-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; dspStart = true; ringMapAudit = true; ringAttachAudit = true; ringDmaAudit = true; };
      nixosModules.fullio-sink-readback-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; vphxAudit = true; ringMapAudit = true; ringAttachAudit = true; holdAtDiscovery = true; sinkReadback = true; };
      nixosModules.fullio-ring-attach-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; vphxAudit = true; ringMapAudit = true; ringAttachAudit = true; };
      nixosModules.fullio-ring-map-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; vphxAudit = true; ringMapAudit = true; };
      nixosModules.fullio-vphx-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; vphxAudit = true; };
      nixosModules.fullio-sink-bank-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          { dspPrepare = true; vphxAudit = true; sinkBankAudit = true; };
      nixosModules.fullio-dsp-start-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
          };
      nixosModules.fullio-sidechain-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
          };
      nixosModules.fullio-immediate-taps-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            immediateTaps = true;
          };
      nixosModules.fullio-routed-taps-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            immediateTaps = true;
            holdAtDiscovery = true;
            gainAudit = true;
            paStopAudit = true;
          };
      nixosModules.fullio-dsp-stop-fault-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            stopFault = true;
          };
      nixosModules.fullio-sidechain-pm-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            holdAtDiscovery = true;
          };
      nixosModules.fullio-pa-off-gain-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            holdAtDiscovery = true;
            gainAudit = true;
          };
      nixosModules.fullio-pa-off-teardown-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            holdAtDiscovery = true;
            gainAudit = true;
            paStopAudit = true;
          };
      nixosModules.fullio-pa-off-missing-stop-proof =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            holdAtDiscovery = true;
            gainAudit = true;
            paStopAudit = true;
            faultWorker = true;
            missingStopProof = true;
          };
      nixosModules.fullio-pa-off-codec-guard-audit =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            holdAtDiscovery = true;
            gainAudit = true;
            paStopAudit = true;
            faultWorker = true;
            codecGuardAudit = true;
          };
      nixosModules.fullio-pa-off-fault-worker =
        import ./modules/denali/fullio-clock-off-audit.nix packages.${system}
          {
            dspPrepare = true;
            dspStart = true;
            sidechain = true;
            holdAtDiscovery = true;
            gainAudit = true;
            paStopAudit = true;
            faultWorker = true;
          };
      nixosModules.fullio-feedback-vi =
        import ./modules/denali/fullio-feedback-probe.nix packages.${system} "vi"
          null;
      nixosModules.fullio-feedback-cps =
        import ./modules/denali/fullio-feedback-probe.nix packages.${system} "cps"
          null;
      nixosModules.fullio-feedback-cps-wake =
        import ./modules/denali/fullio-feedback-probe.nix packages.${system} "cps"
          "wake";
      nixosModules.fullio-feedback-cps-offset2 =
        import ./modules/denali/fullio-feedback-probe.nix packages.${system} "cps"
          "offset2";
      packages.${system} = rec {
        default = kernel;
        fullio-reference-topology = pkgs.callPackage ./pkgs/fullio-topology.nix { };
        fullio-reference-volume = pkgs.callPackage ./pkgs/fullio-reference-volume.nix { };
        fullio-feedback-probes = pkgs.callPackage ./pkgs/fullio-topology.nix { feedbackProbes = true; };
        # Compile-only porting target. Not selected by the Denali NixOS module;
        # the FullIO machine links, topology and protection are not yet ported.
        fullio-capture-kernel = kernel.override {
          localVersion = "-surface-fullio-capture-test";
          kernelPatches = kernel.kernelPatches ++ [
            {
              name = "sp11-fullio-next-capture";
              patch = ./pkgs/patches/sp11-fullio-next-capture.patch;
            }
            {
              name = "sp11-fullio-capture-dt";
              patch = ./pkgs/patches/sp11-fullio-capture-dt.patch;
            }
            {
              name = "sp11-lpass-tx-stereo-decimators";
              patch = ./pkgs/patches/sp11-lpass-tx-stereo-decimators.patch;
            }
          ];
        };
        # Intel/MIPI core, Qualcomm DSP and codec interfaces compile together,
        # but no board node yet opts in to the feedback routes.
        fullio-feedback-kernel = fullio-capture-kernel.override {
          localVersion = "-surface-fullio-feedback-test";
          kernelPatches =
            fullio-capture-kernel.kernelPatches
            ++
              map
                (patch: {
                  name = builtins.baseNameOf patch;
                  inherit patch;
                })
                [
                  ./pkgs/patches/sp11-fullio-q6-feedback.patch
                  ./pkgs/patches/sp11-fullio-machine-feedback.patch
                  ./pkgs/patches/sp11-fullio-wsa-macro-feedback.patch
                  ./pkgs/patches/sp11-fullio-sdw-simple-feedback.patch
                  ./pkgs/patches/sp11-fullio-wsa884x-feedback.patch
                  ./pkgs/patches/sp11-fullio-qcom-feedback.patch
                  ./pkgs/patches/sp11-fullio-dsp-parser.patch
                  ./pkgs/patches/sp11-fullio-dsp-ctrl-links.patch
                  ./pkgs/patches/sp11-fullio-dsp-containers.patch
                  ./pkgs/patches/sp11-fullio-dsp-ownership.patch
                  ./pkgs/patches/sp11-fullio-dsp-graph-lifecycle.patch
                  ./pkgs/patches/sp11-fullio-feedback-lifetime.patch
                  ./pkgs/patches/sp11-fullio-dsp-oob-map.patch
                  ./pkgs/patches/sp11-fullio-dsp-fe-dma.patch
                  ./pkgs/patches/sp11-fullio-dsp-cal-transport.patch
                  ./pkgs/patches/sp11-fullio-dsp-stage-index.patch
                  ./pkgs/patches/sp11-fullio-dsp-fe-preflight.patch
                  ./pkgs/patches/sp11-fullio-dsp-companion-backends.patch
                  ./pkgs/patches/sp11-fullio-dsp-readback.patch
                  ./pkgs/patches/sp11-fullio-dsp-verify-tag.patch
                  ./pkgs/patches/sp11-fullio-dsp-cal-sequence.patch
                  ./pkgs/patches/sp11-fullio-wsa884x-pa-readback.patch
                  ./pkgs/patches/sp11-fullio-dsp-muted-preflight.patch
                  ./pkgs/patches/sp11-fullio-graph-dedup.patch
                  ./pkgs/patches/sp11-fullio-dsp-media-prelude.patch
                  ./pkgs/patches/sp11-fullio-dsp-mfc-wire-size.patch
                  ./pkgs/patches/sp11-fullio-dsp-stage-logs.patch
                  ./pkgs/patches/sp11-fullio-dsp-bootstrap-write-only.patch
                  ./pkgs/patches/sp11-fullio-feedback-capture-fe.patch
                  ./pkgs/patches/sp11-fullio-feedback-capture-backends.patch
                  ./pkgs/patches/sp11-fullio-wsa884x-diagnostic-pa-state.patch
                  ./pkgs/patches/sp11-fullio-wsa884x-pa-epoch.patch
                  ./pkgs/patches/sp11-fullio-wsa884x-pa-ready.patch
                  ./pkgs/patches/sp11-fullio-checked-protection-clocks.patch
                  ./pkgs/patches/sp11-fullio-dsp-hard-mute.patch
                  ./pkgs/patches/sp11-fullio-dsp-mute-readback.patch
                  ./pkgs/patches/sp11-fullio-dsp-mute-response-header.patch
                  ./pkgs/patches/sp11-fullio-dsp-mute-compact-readback.patch
                  ./pkgs/patches/sp11-fullio-feedback-probe-pa-check.patch
                  ./pkgs/patches/sp11-fullio-card-amp-pair.patch
                  ./pkgs/patches/sp11-fullio-graph-mute-evidence.patch
                  ./pkgs/patches/sp11-fullio-post-pa-pair-guard.patch
                  ./pkgs/patches/sp11-fullio-clock-off-before-pa-teardown.patch
                  ./pkgs/patches/sp11-fullio-verify-pa-shutdown.patch
                  ./pkgs/patches/sp11-fullio-clock-off-feedback-free.patch
                  ./pkgs/patches/sp11-fullio-clock-off-audit.patch
                  ./pkgs/patches/sp11-fullio-dsp-prepare-audit.patch
                  ./pkgs/patches/sp11-fullio-dsp-start-audit.patch
                  ./pkgs/patches/sp11-fullio-dsp-start-audit-zero-ring.patch
                  ./pkgs/patches/sp11-fullio-cps-probe-wake.patch
                  ./pkgs/patches/sp11-fullio-cps-probe-active-offset.patch
                  ./pkgs/patches/sp11-fullio-integrated-sidechain-audit.patch
                  ./pkgs/patches/sp11-fullio-immediate-taps-audit.patch
                  ./pkgs/patches/sp11-fullio-dsp-stop-fault-audit.patch
                  ./pkgs/patches/sp11-fullio-pa-off-gain-audit.patch
                  ./pkgs/patches/sp11-fullio-pa-off-teardown-audit.patch
                  ./pkgs/patches/sp11-fullio-pa-off-fault-worker.patch
                  ./pkgs/patches/sp11-wsa884x-runtime-pm-lifetime.patch
                  ./pkgs/patches/sp11-fullio-pa-off-codec-guard-audit.patch
                  ./pkgs/patches/sp11-fullio-capture-only-open.patch
                  ./pkgs/patches/sp11-fullio-swrm-pm-transition-audit.patch
                  ./pkgs/patches/sp11-fullio-stop-proof-verdict.patch
                  ./pkgs/patches/sp11-fullio-swrm-link-gate.patch
                  ./pkgs/patches/sp11-fullio-pre-pm-open-gate.patch
                  ./pkgs/patches/sp11-fullio-v33-vi-order.patch
                  ./pkgs/patches/sp11-fullio-clash-snapshot.patch
                  ./pkgs/patches/sp11-fullio-v19c-final-gain-frame.patch
                  ./pkgs/patches/sp11-fullio-pm-preconditions.patch
                  ./pkgs/patches/sp11-fullio-feedback-pair.patch
                  ./pkgs/patches/sp11-fullio-detach-latch.patch
                  ./pkgs/patches/sp11-fullio-tap-host-window.patch
                  ./pkgs/patches/sp11-fullio-broadcast-timeout.patch
                  ./pkgs/patches/sp11-fullio-resume-slots.patch
                  ./pkgs/patches/sp11-fullio-clock-stop-entry-latch.patch
                  ./pkgs/patches/sp11-fullio-resume-boundaries.patch
                  ./pkgs/patches/sp11-fullio-resume-irq-mask-audit.patch
                  ./pkgs/patches/sp11-fullio-clock-stop-finished-audit.patch
                  ./pkgs/patches/sp11-fullio-resume-admission.patch
                  ./pkgs/patches/sp11-fullio-frame-stop.patch
                  ./pkgs/patches/sp11-fullio-clock-stop-quarantine.patch
                  ./pkgs/patches/sp11-fullio-wsa-ready-watchdog.patch
                  ./pkgs/patches/sp11-swr-master-port-bound.patch
                  ./pkgs/patches/sp11-fullio-vphx-audit.patch
                  ./pkgs/patches/sp11-fullio-sink-fields.patch
                  ./pkgs/patches/sp11-fullio-sink-bank-audit.patch
                  ./pkgs/patches/sp11-fullio-vi-descriptor.patch
                  ./pkgs/patches/sp11-fullio-v33-pair-order.patch
                  ./pkgs/patches/sp11-fullio-clock-proof.patch
                  ./pkgs/patches/sp11-fullio-stop-keep-gain-cap.patch
                  ./pkgs/patches/sp11-fullio-stop-cap-audit.patch
                  ./pkgs/patches/sp11-fullio-vphx-ready.patch
                  ./pkgs/patches/sp11-fullio-prepare-recheck-tags.patch
                  ./pkgs/patches/sp11-fullio-scope-mute-ticket.patch
                  ./pkgs/patches/sp11-fullio-latch-shutdown-proof.patch
                  ./pkgs/patches/sp11-fullio-latch-dsp-stop.patch
                  ./pkgs/patches/sp11-fullio-ring-map-pair.patch
                  ./pkgs/patches/sp11-fullio-ring-owner.patch
                  ./pkgs/patches/sp11-fullio-global-oob-token.patch
                  ./pkgs/patches/sp11-fullio-ring-map-audit.patch
                  ./pkgs/patches/sp11-fullio-graph-close-proof.patch
                  ./pkgs/patches/sp11-fullio-ring-attach-audit.patch
                  ./pkgs/patches/sp11-fullio-ring-dma-audit.patch
                  ./pkgs/patches/sp11-fullio-pull-config-parity.patch
                  ./pkgs/patches/sp11-fullio-ring-dma-taps.patch
                  ./pkgs/patches/sp11-fullio-no-legacy-map-audit.patch
                  ./pkgs/patches/sp11-fullio-pull-events.patch
                  ./pkgs/patches/sp11-fullio-capture-only-no-render-backing.patch
                  ./pkgs/patches/sp11-fullio-mix-unity-cap.patch
                  ./pkgs/patches/sp11-fullio-sink-readback-audit.patch
                  ./pkgs/patches/sp11-fullio-ring-no-pcm-callback.patch
                  ./pkgs/patches/sp11-fullio-ring-byte-cursor.patch
                  ./pkgs/patches/sp11-fullio-soft-cycle-audit.patch
                  ./pkgs/patches/sp11-fullio-logger-readback.patch
                  ./pkgs/patches/sp11-fullio-dsp-gain-readback.patch
                  ./pkgs/patches/sp11-fullio-native-endpoint-controls.patch
                  ./pkgs/patches/sp11-fullio-ring-cursor-snapshot.patch
                  ./pkgs/patches/sp11-fullio-pull-prepare.patch
                  ./pkgs/patches/sp11-fullio-pull-watermark.patch
                  ./pkgs/patches/sp11-fullio-pcm-watermark-work.patch
                  ./pkgs/patches/sp11-fullio-pcm-pointer.patch
                  ./pkgs/patches/sp11-fullio-pcm-dma.patch
                  ./pkgs/patches/sp11-fullio-pull-state.patch
                  ./pkgs/patches/sp11-fullio-native-prepare.patch
                  ./pkgs/patches/sp11-fullio-native-trigger.patch
                  ./pkgs/patches/sp11-fullio-native-render-count.patch
                  ./pkgs/patches/sp11-fullio-wsa-reference-cold.patch
                  ./pkgs/patches/sp11-fullio-wsa-reference-stop.patch
                  ./pkgs/patches/sp11-fullio-wsa-reference-start.patch
                  ./pkgs/patches/sp11-fullio-reference-cps-port.patch
                  ./pkgs/patches/sp11-fullio-wsa-start-settle.patch
                  ./pkgs/patches/sp11-fullio-wsa-cold-resume.patch
                ];
        };
        fullio-muted-kernel = fullio-feedback-kernel.override {
          localVersion = "-surface-fullio-muted-test";
          kernelPatches = fullio-feedback-kernel.kernelPatches ++ [
            {
              name = "sp11-fullio-feedback-dt";
              patch = ./pkgs/patches/sp11-fullio-feedback-dt.patch;
            }
            {
              name = "sp11-fullio-muted-fixture";
              patch = ./pkgs/patches/sp11-fullio-muted-fixture.patch;
            }
            {
              name = "sp11-fullio-reference-render-topology";
              patch = ./pkgs/patches/sp11-fullio-reference-render-topology.patch;
            }
            {
              name = "sp11-fullio-reference-render-pa-range";
              patch = ./pkgs/patches/sp11-fullio-reference-render-pa-range.patch;
            }
          ];
        };
        fullio-feedback-probe-kernel = fullio-muted-kernel.override {
          localVersion = "-surface-fullio-feedback-probe";
          kernelPatches = fullio-muted-kernel.kernelPatches ++ [
            {
              name = "sp11-fullio-feedback-probe-dt";
              patch = ./pkgs/patches/sp11-fullio-feedback-probe-dt.patch;
            }
            {
              name = "sp11-fullio-probe-native-endpoint";
              patch = ./pkgs/patches/sp11-fullio-probe-native-endpoint.patch;
            }
            {
              name = "sp11-fullio-cps-source-first";
              patch = ./pkgs/patches/sp11-fullio-cps-source-first.patch;
            }
          ];
        };
      };
      devShells.${system}.surface-next = pkgs.mkShell {
        inputsFrom = [ kernel ];
        nativeBuildInputs = [
          pkgs.util-linux
        ];
        SURFACE_NEXT_SOURCE = kernel.src;
        SURFACE_NEXT_CONFIG = kernel.configfile;
        SURFACE_NEXT_RELEASE = kernel.modDirVersion;
        SURFACE_NEXT_LOCALVERSION = "-surface-touch";
        SURFACE_NEXT_PATCHES = nixpkgs.lib.concatMapStringsSep " " (
          p: toString p.patch
        ) kernel.kernelPatches;
        inherit (kernel.env) RUST_LIB_SRC;
      };
    };
}
