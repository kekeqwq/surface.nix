{
  config,
  lib,
  pkgs,
  ...
}:
{
  imports = [
    ./denali/kernel.nix
    ./denali/firmware.nix
    ./denali/boot.nix
    ./denali/bluetooth.nix
  ];

  options.surface.devices.denali = {
    enable = lib.mkEnableOption "Microsoft Surface Pro 11 Denali non-5G OLED hardware support";
    keyboard.hhkb.enable = lib.mkEnableOption ''
      the experimental HHKB layer on the verified Denali magnetic keyboard
    '';
    niriOutputs = lib.mkOption {
      type = lib.types.lines;
      readOnly = true;
      default = ''
        output "eDP-1" {
            mode "2880x1920@120.000"
            scale 2
        }
      '';
      description = "Native OLED output declaration for a host's Niri configuration. Does not enable a desktop.";
    };
  };

  config = lib.mkIf config.surface.devices.denali.enable {
    assertions = [
      {
        assertion = pkgs.stdenv.hostPlatform.system == "aarch64-linux";
        message = "Surface Pro 11 Denali requires aarch64-linux.";
      }
    ];
    nixpkgs.overlays = [ (import ../overlay.nix) ];
  };
}
