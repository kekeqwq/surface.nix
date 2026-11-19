{ config, lib, pkgs, ... }:
let
  cfg = config.surface.devices.denali;
in
{
  options.surface.devices.denali.kernel = lib.mkOption {
    type = lib.types.enum [ "linux-sp11" "surface-next" "surface-next-touch" ];
    default = "linux-sp11";
    description = "Denali kernel track. surface-next is an unmodified kernel.org snapshot; surface-next-touch adds the experimental SPI-HID/QSPI digitizer queue.";
  };

  config = lib.mkIf cfg.enable {
    boot.kernelPackages = lib.mkDefault (
      if cfg.kernel == "surface-next-touch" then pkgs.surfacePackages.surfaceNextTouchPackages
      else if cfg.kernel == "surface-next" then pkgs.surfacePackages.surfaceNextPackages
      else pkgs.surfacePackages.linuxPackages
    );
    boot.initrd.availableKernelModules = {
      # Both USB-C PHYs reference the modular TCSR clock provider in the DTB.
      tcsrcc-x1e80100 = true;
      phy-qcom-qmp-pcie = true;
      phy-snps-eusb2 = true;
      phy-qcom-eusb2-repeater = true;
      phy-qcom-qmp-combo = true;
      phy-qcom-edp = true;
      panel-samsung-atna33xc20 = true;
      msm = true;
      surface_hid = true;
      xhci_pci = true;
      usb_storage = true;
      uas = true;
      # The pinned kernel does not include the generic PROM21 xHCI quirk.
      xhci_pci_prom21 = lib.mkOverride 90 false;
    };
    boot.kernelParams = [ "clk_ignore_unused" "pd_ignore_unused" ];
    hardware.deviceTree = {
      enable = true;
      name = "qcom/x1e80100-microsoft-denali-oled.dtb";
      filter = "x1e80100-microsoft-denali-oled.dtb";
    };
  };
}
