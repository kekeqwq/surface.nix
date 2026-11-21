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
    boot.initrd.availableKernelModules = {
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
      xhci_pci_prom21 = lib.mkOverride 90 false;
    }
    // lib.genAttrs [
      # The device uses NVMe; these generic suggestions are absent from its
      # audited Kconfig. Keep missing-module checks strict.
      "ahci"
      "ata_piix"
      "mmc_block"
      "pata_marvell"
      "sata_nv"
      "sata_sis"
      "sata_uli"
      "sata_via"
    ] (_: lib.mkOverride 90 false);
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
