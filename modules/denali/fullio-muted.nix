packages:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  topology = pkgs.runCommand "denali-fullio-muted-topology" { } ''
    install -Dm644 ${packages.fullio-reference-topology}/share/sp11-fullio/v19c.bin \
      "$out/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0-tplg.bin"
  '';
  captureUcm = pkgs.surfacePackages.alsaUcm.overrideAttrs (old: {
    postInstall = (old.postInstall or "") + ''
      ucm="$out/share/alsa/ucm2/Qualcomm/x1e80100"
      rm "$ucm/MICROSOFT-Surface-Pro-11.conf"
      install -m644 ${./fullio-mic-ucm.conf} "$ucm/Surface11-FullIO-Mic.conf"
      cat > "$ucm/MICROSOFT-Surface-Pro-11.conf" <<'EOF'
      Syntax 4
      SectionUseCase."HiFi" {
          File "/Qualcomm/x1e80100/Surface11-FullIO-Mic.conf"
          Comment "MicArray only (FullIO muted test)"
      }
      EOF
    '';
  });
in
{
  assertions = [
    {
      assertion =
        config.surface.devices.denali.enable && pkgs.stdenv.hostPlatform.system == "aarch64-linux";
      message = "The FullIO muted fixture requires an enabled ARM64 Denali configuration.";
    }
  ];
  boot.kernelPackages = lib.mkForce (pkgs.linuxPackagesFor packages.fullio-muted-kernel);
  hardware.firmware = [ (lib.hiPrio topology) ];
  systemd.user.services.wireplumber.environment.ALSA_CONFIG_UCM2 =
    lib.mkForce "${captureUcm}/share/alsa/ucm2";
  # Do not let the session probe or activate an automatic speaker profile.
  # Use raw ALSA for controlled enumeration and capture diagnostics first.
  services.pipewire.wireplumber.extraConfig."51-surface-speaker" = lib.mkForce {
    "monitor.alsa.rules" = [
      {
        matches = [ { "device.name" = "alsa_card.platform-sound"; } ];
        actions.update-props."device.profile" = "off";
      }
    ];
  };
}
