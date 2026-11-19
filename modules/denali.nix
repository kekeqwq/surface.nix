{ config, lib, pkgs, ... }:
let
  cfg = config.surface.devices.denali;
in
{
  imports = [
    ./denali/kernel.nix
    ./denali/firmware.nix
  ];

  options.surface.devices.denali.enable = lib.mkEnableOption "Microsoft Surface Pro 11 Denali (non-5G OLED) hardware support";

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = pkgs.stdenv.hostPlatform.system == "aarch64-linux";
        message = "Surface Pro 11 Denali requires aarch64-linux.";
      }
    ];
    nixpkgs.overlays = [ (import ../overlay.nix) ];
  };
}
