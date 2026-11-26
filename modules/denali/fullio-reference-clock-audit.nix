# Layer only on an existing protected FullIO render configuration.
packages:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  baseline =
    if config.surface.fullio.checkedCapture or false then
      packages.fullio-checked-capture-kernel
    else
      packages.fullio-reference-kernel;
  auditKernel = import ./with-hhkb.nix {
    enabled = config.surface.devices.denali.keyboard.hhkb.enable or false;
    kernel = baseline.override {
      kernelPatches = baseline.kernelPatches ++ [
        {
          name = "denali-fullio-live-clock-readback";
          patch = ../../pkgs/patches/denali-fullio-live-clock-readback.patch;
        }
      ];
    };
  };
in
lib.mkIf (config.surface.fullio.referenceRender.enable or true) {
  assertions = [
    {
      assertion =
        config.surface.devices.denali.enable && pkgs.stdenv.hostPlatform.system == "aarch64-linux";
      message = "FullIO live clock readback is an AArch64 Denali diagnostic.";
    }
  ];
  boot.kernelPackages = lib.mkOverride 40 (pkgs.linuxPackagesFor auditKernel);
  boot.extraModprobeConfig = ''
    options snd_soc_lpass_wsa_macro fullio_level_audit=1
    options snd_q6apm fullio_gain_audit=1
  '';
}
