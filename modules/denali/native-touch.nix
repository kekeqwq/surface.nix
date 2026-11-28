{
  kernel,
  touchModule,
  touchDtbs,
  additionalVariants ? [ ],
}:
{
  config,
  lib,
  ...
}:
let
  cfg = config.surface.devices.denali;
  dtb = "qcom/x1e80100-microsoft-denali-oled.dtb";
  variant = lib.findFirst (v: v.kernel.drvPath == config.boot.kernelPackages.kernel.drvPath) null (
    [ { inherit kernel touchModule; } ] ++ additionalVariants
  );
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
        assertion = variant != null;
        message = "Denali native touch requires a locked denaliDailyBoot kernel variant.";
      }
      {
        assertion = config.hardware.deviceTree.name == dtb;
        message = "Denali native touch requires the non-5G OLED device tree.";
      }
    ];
    hardware.deviceTree.package = lib.mkForce touchDtbs;
    boot.extraModulePackages = lib.optional (variant != null) variant.touchModule;
    # Module selection happens via the new DT's OF modalias after reboot;
    # don't request a modules-load restart or bind/unbind the active controller.
    services.iptsd.enable = lib.mkForce false;
  };
}
