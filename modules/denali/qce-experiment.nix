{
  kernel,
  stockQceDtbs,
  nativeQceDtbs,
  nativeQceIceDtbs,
  nativeQceIceThermalDtbs,
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
    cpuThermalGuard = lib.mkEnableOption ''
      the Denali OLED 85°C passive CPU frequency guard on the validated native-touch/QCE/ICE DTB
    '';
  };

  config = lib.mkIf (cfg.power.disableUnusedQce || cfg.power.disableUnusedUfsIce || cfg.power.cpuThermalGuard) {
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
      {
        assertion = !cfg.power.cpuThermalGuard || cfg.power.disableUnusedUfsIce;
        message = "The Denali thermal guard requires the validated native-touch/QCE/ICE DTB.";
      }
    ];
    # Each derivative validates its device-tree changes against its own parent.
    hardware.deviceTree.package = lib.mkOverride 40 (
      if cfg.power.cpuThermalGuard then
        nativeQceIceThermalDtbs
      else if cfg.power.disableUnusedUfsIce then
        nativeQceIceDtbs
      else if cfg.touchscreen.native.enable then
        nativeQceDtbs
      else
        stockQceDtbs
    );
  };
}
