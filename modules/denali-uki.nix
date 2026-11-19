{ config, lib, ... }:
let
  zboot = config.boot.kernelPackages.rebuildImage { target = "vmlinuz.efi"; };
in
{
  imports = [ ./denali.nix ];
  config = lib.mkIf config.surface.devices.denali.enable {
    boot.initrd.kernelModules = [ "simpledrm" ];
    boot.kernelParams = [ "arm64.nopauth" "systemd.mask=tpm2.target" "systemd.tpm2_wait=0" ];
    boot.uki.settings.UKI = {
      Linux = "${zboot}/vmlinuz.efi";
      HWIDs = "";
    };
  };
}
