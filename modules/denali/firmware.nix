{ config, lib, pkgs, ... }:
{
  config = lib.mkIf config.surface.devices.denali.enable {
    hardware.firmware = [
      (lib.hiPrio pkgs.surfacePackages.wifiBoard)
      pkgs.linux-firmware
      pkgs.wireless-regdb
    ];
  };
}
