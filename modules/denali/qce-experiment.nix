{
  kernel,
  stockQceDtbs,
  nativeQceDtbs,
  nativeQceIceDtbs,
  additionalKernels ? [ ],
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
  options.surface.devices.denali.power = {
    disableUnusedQce = lib.mkEnableOption ''
      the Denali OLED power experiment which disables the unused QCE device tree node
    '';
    disableUnusedUfsIce = lib.mkEnableOption ''
      the Denali OLED power experiment which disables the ICE used only by disabled UFS
    '';
  };

  config = lib.mkIf (cfg.power.disableUnusedQce || cfg.power.disableUnusedUfsIce) {
    assertions = [
      {
        assertion =
          cfg.enable
          && lib.any (k: k.drvPath == config.boot.kernelPackages.kernel.drvPath) (
            [ kernel ] ++ additionalKernels
          )
          && config.hardware.deviceTree.name == "qcom/x1e80100-microsoft-denali-oled.dtb";
        message = "The QCE/ICE experiments require the locked Denali OLED daily kernel and DTB.";
      }
      {
        assertion =
          !cfg.power.disableUnusedUfsIce || (cfg.power.disableUnusedQce && cfg.touchscreen.native.enable);
        message = "The unused UFS ICE experiment requires the native touch and QCE experimental DTB.";
      }
    ];
    # Compose with either touch variant, overriding the native-touch DTB only.
    # The derivation proves the QCE status is the sole device-tree change.
    hardware.deviceTree.package = lib.mkOverride 40 (
      if cfg.power.disableUnusedUfsIce then
        nativeQceIceDtbs
      else if cfg.touchscreen.native.enable then
        nativeQceDtbs
      else
        stockQceDtbs
    );
  };
}
