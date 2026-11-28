{
  kernel,
  touchModule,
  touchDtbs,
}:
{
  config,
  lib,
  ...
}:
let
  cfg = config.surface.devices.denali;
  dtb = "qcom/x1e80100-microsoft-denali-oled.dtb";
in
{
  options.surface.devices.denali.touchscreen.native.enable = lib.mkEnableOption ''
    the experimental Denali OLED kernel finger-touch driver (no iptsd; no pen support)
  '';

  config = lib.mkIf cfg.touchscreen.native.enable {
    assertions = [
      {
        assertion = cfg.enable;
        message = "Denali native touch requires Denali hardware support.";
      }
      {
        assertion = config.boot.kernelPackages.kernel.drvPath == kernel.drvPath;
        message = "Denali native touch requires the locked denaliDailyBoot kernel ABI.";
      }
      {
        assertion = config.hardware.deviceTree.name == dtb;
        message = "Denali native touch requires the non-5G OLED device tree.";
      }
    ];
    hardware.deviceTree.package = lib.mkForce touchDtbs;
    boot.extraModulePackages = [ touchModule ];
    # Module selection happens via the new DT's OF modalias after reboot;
    # don't request a modules-load restart or bind/unbind the active controller.
    services.iptsd.enable = lib.mkForce false;
  };
}
