{ kernelPackages }:
{
  config,
  lib,
  ...
}:
let
  cfg = config.surface.devices.denali;
in
{
  options.surface.devices.denali.power.orderFsgenResume = lib.mkEnableOption ''
    the Denali OLED VA-before-WSA system sleep ordering experiment
  '';

  config = lib.mkIf cfg.power.orderFsgenResume {
    assertions = [
      {
        assertion =
          cfg.enable
          && cfg.keyboard.hhkb.enable
          && config.hardware.deviceTree.name == "qcom/x1e80100-microsoft-denali-oled.dtb";
        message = "The fsgen resume order experiment requires the locked FullIO Denali OLED/HHKB baseline.";
      }
    ];
    # Select the explicit variant ahead of the host's normal dailyBoot kernel.
    boot.kernelPackages = lib.mkOverride 25 kernelPackages;
  };
}
