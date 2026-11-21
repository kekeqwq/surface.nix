{
  config,
  lib,
  pkgs,
  ...
}:
{
  config = lib.mkIf config.surface.devices.denali.enable {
    # The opted-in Denali device needs its kernel instead of a desktop default.
    boot.kernelPackages = pkgs.surfacePackages.kernelPackages;

    # Explicit Denali initrd drivers for boot, display, input and rescue media.
    # NVMe, ext4, xHCI, usbhid and hid-generic are built into this kernel.
    boot.initrd.includeDefaultModules = false;
    boot.initrd.availableKernelModules = {
      # PCIe/NVMe and USB PHYs + TCSR clock used by both USB-C ports.
      tcsrcc-x1e80100 = true;
      phy-qcom-qmp-pcie = true;
      phy-snps-eusb2 = true;
      phy-qcom-eusb2-repeater = true;
      phy-qcom-qmp-combo = true;
      phy-qcom-edp = true;
      # Early display for Plymouth.
      msm = true;
      panel-samsung-atna33xc20 = true;
      # Surface keyboard/HID (Surface Aggregator) and USB storage for rescue.
      surface_hid = true;
      usb_storage = true;
      uas = true;
      sr_mod = true;
      vfat = true;
    };

    boot.kernelParams = [
      "clk_ignore_unused"
      "pd_ignore_unused"
    ];
    hardware.deviceTree = {
      enable = true;
      name = "qcom/x1e80100-microsoft-denali-oled.dtb";
      filter = "x1e80100-microsoft-denali-oled.dtb";
    };
    services.iptsd.enable = lib.mkDefault true;
  };
}
