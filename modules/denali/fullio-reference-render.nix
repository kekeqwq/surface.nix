packages:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  dtb = "x1e80100-microsoft-denali-oled.dtb";
  renderDtbs =
    pkgs.runCommand "denali-fullio-reference-render-dtbs"
      {
        nativeBuildInputs = [ pkgs.dtc ];
      }
      ''
        install -Dm644 ${packages.fullio-reference-kernel}/dtbs/qcom/${dtb} "$out/qcom/${dtb}"
        # The native protected render route replaces the silent fixture marker.
        fdtget "$out/qcom/${dtb}" /sound microsoft,denali-fullio-muted-test
        fdtput -d "$out/qcom/${dtb}" /sound microsoft,denali-fullio-muted-test
        fdtput "$out/qcom/${dtb}" /sound microsoft,denali-fullio-reference-render
        swr=/soc@0/soundwire@6b10000
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
    install -Dm644 ${packages.fullio-reference-topology}/share/sp11-fullio/v19c.bin \
      "$out/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0-tplg.bin"
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
  sessionState = "%h/.local/state/fullio-audio-session";
in
{
  assertions = [
    {
      assertion =
        config.surface.devices.denali.enable && pkgs.stdenv.hostPlatform.system == "aarch64-linux";
      message = "The FullIO reference render fixture requires an enabled ARM64 Denali configuration.";
    }
  ];
  boot.kernelPackages = lib.mkForce (pkgs.linuxPackagesFor packages.fullio-reference-kernel);
  hardware.deviceTree = {
    name = lib.mkForce "qcom/${dtb}";
    filter = lib.mkForce dtb;
    dtbSource = renderDtbs;
  };
  hardware.firmware = [ (lib.hiPrio topology) ];
  # Endpoint volume/mute arming helper (tlv_write + pinned GainStep table).
  environment.systemPackages = [
    packages.fullio-reference-volume
    audioTools
  ];
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
        wantedBy = [ "default.target" ];
        path = sessionPath;
        serviceConfig = {
          ExecStart = "${audioTools}/bin/fullio-graph-holder ${sessionState}";
          Restart = "on-failure";
          RestartSec = "2";
        };
      };
      fullio-endpoint-keeper = {
        description = "Re-apply the pinned FullIO endpoint transaction per graph";
        wantedBy = [ "default.target" ];
        path = sessionPath;
        serviceConfig = {
          ExecStart = "${audioTools}/bin/fullio-endpoint-keeper ${sessionState}";
          Restart = "on-failure";
          RestartSec = "2";
        };
      };
      # One-shot sessions must not persist WirePlumber profile choices into
      # keke's Gen20 state.
      wireplumber.environment = {
        ALSA_CONFIG_UCM2 = lib.mkOverride 40 "${renderUcm}/share/alsa/ucm2";
        XDG_STATE_HOME = lib.mkOverride 40 "%t/fullio-reference-render-state";
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
}
