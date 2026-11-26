packages:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  dtb = "x1e80100-microsoft-denali-oled.dtb";
  feedbackParity = config.surface.fullio.feedbackParityAudit || config.surface.fullio.feedbackParityRender;
  kernel = import ./with-hhkb.nix {
    enabled = config.surface.devices.denali.keyboard.hhkb.enable or false;
    kernel =
      if config.surface.fullio.checkedCapture then
        packages.fullio-checked-capture-kernel
      else
        packages.fullio-reference-kernel;
  };
  renderDtbs =
    pkgs.runCommand "denali-fullio-reference-render-dtbs"
      {
        nativeBuildInputs = [ pkgs.dtc ];
      }
      ''
        install -Dm644 ${kernel}/dtbs/qcom/${dtb} "$out/qcom/${dtb}"
        # The native protected render route replaces the silent fixture marker.
        fdtget "$out/qcom/${dtb}" /sound microsoft,denali-fullio-muted-test
        fdtput -d "$out/qcom/${dtb}" /sound microsoft,denali-fullio-muted-test
        fdtput "$out/qcom/${dtb}" /sound microsoft,denali-fullio-reference-render
        ${lib.optionalString config.surface.fullio.checkedCapture ''
          fdtput "$out/qcom/${dtb}" /sound microsoft,denali-fullio-checked-capture
          fdtget "$out/qcom/${dtb}" /sound microsoft,denali-fullio-checked-capture
        ''}
        ${lib.optionalString config.surface.fullio.preSpLoggerAudit ''
          fdtput "$out/qcom/${dtb}" /sound microsoft,denali-fullio-pre-sp-logger-audit
          fdtget "$out/qcom/${dtb}" /sound microsoft,denali-fullio-pre-sp-logger-audit
        ''}
        swr=/soc@0/soundwire@6b10000
        ${lib.optionalString config.surface.fullio.swrResumeAudit ''
          fdtget "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-feedback
          fdtput "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-pm-transition-audit
          fdtput "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-link-gate
          fdtput "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-wait-frame-stop
          fdtget "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-pm-transition-audit
          fdtget "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-link-gate
          fdtget "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-wait-frame-stop
        ''}
        ${lib.optionalString feedbackParity ''
          fdtget "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-feedback
          fdtput "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-sidechain-audit
          fdtget "$out/qcom/${dtb}" "$swr" qcom,denali-fullio-sidechain-audit
        ''}
        fdtput "$out/qcom/${dtb}" "$swr/speaker@0,0" qcom,denali-fullio-reference-codec
        fdtput "$out/qcom/${dtb}" "$swr/speaker@0,1" qcom,denali-fullio-reference-codec
        fdtget "$out/qcom/${dtb}" /sound microsoft,denali-fullio-reference-render
        fdtget "$out/qcom/${dtb}" "$swr/speaker@0,0" qcom,denali-fullio-reference-codec
        fdtget "$out/qcom/${dtb}" "$swr/speaker@0,1" qcom,denali-fullio-reference-codec
        for property in microsoft,denali-fullio-capture-only microsoft,denali-fullio-post-pa-test \
                        microsoft,denali-fullio-dsp-start-audit microsoft,denali-fullio-ring-map-audit \
                        microsoft,denali-fullio-muted-test; do
          if fdtget "$out/qcom/${dtb}" /sound "$property" 2>/dev/null; then
            echo "reference render fixture cannot use $property" >&2
            exit 1
          fi
        done
        test "$(fdtget "$out/qcom/${dtb}" /sound model)" = "X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0"
      '';
  topology = pkgs.runCommand "denali-fullio-reference-topology" { } ''
    ${if config.surface.fullio.preSpLoggerAudit then ''
      mkdir -p "$out/lib/firmware/qcom/x1e80100"
      cp ${../../tests/fullio-pre-sp-fixture.py} fullio-pre-sp-fixture.py
      cp ${../../tests/fullio-topology.py} fullio-topology.py
      ${lib.getExe pkgs.python3} fullio-pre-sp-fixture.py \
        ${packages.fullio-reference-topology}/share/sp11-fullio/v19c.bin \
        "$out/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0-tplg.bin"
    '' else ''
      install -Dm644 ${packages.fullio-reference-topology}/share/sp11-fullio/v19c.bin \
        "$out/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0-tplg.bin"
    ''}
  '';
  renderUcm = pkgs.surfacePackages.alsaUcm.overrideAttrs (old: {
    postInstall = (old.postInstall or "") + ''
      ucm="$out/share/alsa/ucm2/Qualcomm/x1e80100"
      rm "$ucm/MICROSOFT-Surface-Pro-11.conf"
      install -m644 ${./fullio-reference-ucm.conf} "$ucm/SP11-Reference-Render.conf"
      cat > "$ucm/MICROSOFT-Surface-Pro-11.conf" <<'EOF'
      Syntax 4
      SectionUseCase."HiFi" {
          File "/Qualcomm/x1e80100/SP11-Reference-Render.conf"
          Comment "Stereo speakers (protected FullIO) and MicArray"
      }
      EOF
    '';
  });
  audioTools = pkgs.runCommand "fullio-audio-session-tools" { } ''
    install -Dm755 ${../../scripts/fullio-graph-holder.sh} "$out/bin/fullio-graph-holder"
    install -Dm755 ${../../scripts/fullio-endpoint-keeper.sh} "$out/bin/fullio-endpoint-keeper"
    install -Dm755 ${../../scripts/fullio-reference-volume-once.py} "$out/bin/fullio-reference-volume-once"
  '';
in
{
  options.surface.fullio.checkedCapture = lib.mkEnableOption ''
    Experimental Denali MicArray read completion and STOP ownership checks
  '';
  options.surface.fullio.feedbackParityRender = lib.mkEnableOption ''
    Denali protected desktop render at 0 dB with verified VI/CPS feedback parity
  '';
  options.surface.fullio.feedbackParityAudit = lib.mkEnableOption ''
    Diagnostic-only Golden VI/CPS active-bank and CPS wake parity on Denali
  '';
  options.surface.fullio.preSpLoggerAudit = lib.mkEnableOption ''
    Diagnostic-only Denali topology with the v19c logger moved to SP input
  '';
  options.surface.fullio.swrResumeAudit = lib.mkEnableOption ''
    Denali FullIO SoundWire resume snapshots with fail-closed link admission
  '';
  config = {
    assertions = [
      {
        assertion = !feedbackParity || (
          config.surface.fullio.checkedCapture && config.surface.fullio.swrResumeAudit
          && !config.surface.fullio.preSpLoggerAudit
        );
        message = "Feedback parity requires checked capture, frame-stop admission and the stock topology.";
      }
      {
        assertion = !(config.surface.fullio.feedbackParityAudit && config.surface.fullio.feedbackParityRender);
        message = "Select either feedback parity desktop render or the manual-start audit, not both.";
      }
      {
        assertion = !config.surface.fullio.preSpLoggerAudit || config.surface.fullio.checkedCapture;
        message = "The pre-SP logger diagnostic requires the checked-capture render fixture.";
      }
      {
        assertion =
          config.surface.devices.denali.enable && pkgs.stdenv.hostPlatform.system == "aarch64-linux";
        message = "The FullIO reference render fixture requires an enabled ARM64 Denali configuration.";
      }
    ];
    boot.kernelPackages = lib.mkForce (pkgs.linuxPackagesFor kernel);
    hardware.deviceTree = {
      name = lib.mkForce "qcom/${dtb}";
      filter = lib.mkForce dtb;
      dtbSource = renderDtbs;
    };
    hardware.firmware = [ (lib.hiPrio topology) ];
    # Keep the graph across playback gaps and re-arm the reviewed endpoint
    # transaction after graph reopen. Do not open the MicArray at login.
    systemd.user.services =
      let
        # The scripts shell out to core tools; user units start with a bare PATH.
        sessionPath = with pkgs; [
          bash
          coreutils
          gawk
          gnugrep
          python3
        ];
      in
      {
        fullio-graph-holder = {
          description = "Hold the FullIO render graph alive with a silent stream";
          wantedBy = lib.optional (!config.surface.fullio.preSpLoggerAudit && !config.surface.fullio.feedbackParityAudit) "default.target";
          path = sessionPath;
          serviceConfig = {
            ExecStart = "${audioTools}/bin/fullio-graph-holder ${pkgs.pipewire}/bin/pw-cat";
            RuntimeDirectory = "denali-fullio-holder";
            RuntimeDirectoryMode = "0700";
            Restart = "on-failure";
            RestartSec = "2";
          };
        };
        fullio-endpoint-keeper = {
          description = "Re-apply the pinned FullIO endpoint transaction per graph";
          wantedBy = lib.optional (!config.surface.fullio.preSpLoggerAudit && !config.surface.fullio.feedbackParityAudit) "default.target";
          path = sessionPath;
          serviceConfig = {
            ExecStart = "${audioTools}/bin/fullio-endpoint-keeper ${pkgs.alsa-utils}/bin/amixer ${packages.fullio-reference-volume}${lib.optionalString config.surface.fullio.feedbackParityRender " 0"}";
            # No automatic replay after an interrupted or unacknowledged DSP write.
            Restart = "no";
          };
        };
        # Preserve desktop volume preferences without writing into Gen20's
        # WirePlumber state.
        wireplumber.environment = {
          ALSA_CONFIG_UCM2 = lib.mkOverride 40 "${renderUcm}/share/alsa/ucm2";
          XDG_STATE_HOME = lib.mkOverride 40 "%h/.local/state/denali-fullio";
        };
      };
    services.pipewire.wireplumber.extraConfig."51-surface-speaker" = lib.mkOverride 40 {
      "monitor.alsa.rules" = [
        {
          matches = [
            { "device.name" = "alsa_card.platform-sound"; }
          ];
          actions.update-props = {
            "api.alsa.use-ucm" = true;
            "device.profile" = "HiFi";
            # The independent FullIO PCM is RW-interleaved only.
            "api.alsa.no-mmap" = true;
          };
        }
      ];
    };
  };
}
