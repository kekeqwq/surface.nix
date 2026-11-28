{
  kernel,
  stockQceDtbs,
  nativeQceDtbs,
}:
{
  config,
  lib,
  ...
}:
let
  cfg = config.surface.devices.denali;
in
{
  options.surface.devices.denali.power.disableUnusedQce = lib.mkEnableOption ''
    the Denali OLED power experiment which disables the unused QCE device tree node
  '';

  config = lib.mkIf cfg.power.disableUnusedQce {
    assertions = [
      {
        assertion =
          cfg.enable
          && config.boot.kernelPackages.kernel.drvPath == kernel.drvPath
          && config.hardware.deviceTree.name == "qcom/x1e80100-microsoft-denali-oled.dtb";
        message = "The QCE experiment requires the locked Denali OLED daily kernel and DTB.";
      }
    ];
    # Compose with either touch variant, overriding the native-touch DTB only.
    # The derivation proves the QCE status is the sole device-tree change.
    hardware.deviceTree.package = lib.mkOverride 40 (
      if cfg.touchscreen.native.enable then nativeQceDtbs else stockQceDtbs
    );
  };
}
