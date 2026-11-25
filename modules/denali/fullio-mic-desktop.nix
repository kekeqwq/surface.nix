packages:
{ pmTransitionAudit ? false, passiveLinkAudit ? false, frameStopAudit ? false }:
{ lib, pkgs, ... }:
let
  dtb = "qcom/x1e80100-microsoft-denali-oled.dtb";
  captureDtbs = pkgs.runCommand "denali-fullio-mic-desktop-dtbs" { nativeBuildInputs = [ pkgs.dtc ]; } ''
    install -Dm644 ${packages.fullio-muted-kernel}/dtbs/${dtb} "$out/${dtb}"
    fdtget "$out/${dtb}" /sound microsoft,denali-fullio-muted-test
    fdtput "$out/${dtb}" /sound microsoft,denali-fullio-capture-only
    fdtget "$out/${dtb}" /sound microsoft,denali-fullio-capture-only
    ${lib.optionalString (pmTransitionAudit || passiveLinkAudit) ''
      swr=/soc@0/soundwire@6b10000
      fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-pm-transition-audit
      fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-pm-transition-audit
    ''}
    ${lib.optionalString passiveLinkAudit ''
      fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-feedback
      fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate
      fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate
      if fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-link-gate-test 2>/dev/null; then
        echo 'Passive observation cannot use a seeded link fault' >&2
        exit 1
      fi
    ''}
    ${lib.optionalString frameStopAudit ''
      fdtput "$out/${dtb}" "$swr" qcom,denali-fullio-wait-frame-stop
      fdtget "$out/${dtb}" "$swr" qcom,denali-fullio-wait-frame-stop
    ''}
    for property in microsoft,denali-fullio-post-pa-test microsoft,denali-fullio-dsp-start-audit; do
      if fdtget "$out/${dtb}" /sound "$property" 2>/dev/null; then
        echo "Mic desktop fixture cannot use $property" >&2
        exit 1
      fi
    done
  '';
in
assert !frameStopAudit || passiveLinkAudit;
{
  imports = [ (import ./fullio-muted.nix packages) ];
  hardware.deviceTree.dtbSource = captureDtbs;
  # Never persist the one-shot profile choice into keke's Gen20 state.
  systemd.user.services.wireplumber.environment.XDG_STATE_HOME = "%t/fullio-mic-state";
  # Deliberately overrides the muted calibration fixture's policy; the
  # kernel rejects both kinds of render open before any DSP allocation.
  services.pipewire.wireplumber.extraConfig."51-surface-speaker" = lib.mkOverride 40 {
    "monitor.alsa.rules" = [
      {
        matches = [ { "device.name" = "alsa_card.platform-sound"; } ];
        actions.update-props = {
          "api.alsa.use-ucm" = true;
          "device.profile" = "HiFi";
        };
      }
    ];
  };
}
