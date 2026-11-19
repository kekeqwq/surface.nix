{
  description = "Minimal NixOS hardware support and Live ISO for Surface Pro 11 Denali OLED";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable-small";
    localFiles = {
      url = "path:./local-files";
      flake = false;
    };
  };

  outputs = { nixpkgs, localFiles, ... }:
    let
      system = "aarch64-linux";
      mkLive = private: nixpkgs.lib.nixosSystem {
        modules = [ ./live/uki.nix ] ++ nixpkgs.lib.optional private {
          services.openssh.enable = nixpkgs.lib.mkForce true;
          users.users.nixos.openssh.authorizedKeys.keyFiles = [ (localFiles + "/authorized_keys") ];
        };
      };
      live = mkLive false;
      isolated = nixpkgs.lib.nixosSystem {
        modules = [ ./modules/denali.nix { nixpkgs.hostPlatform = system; } ];
      };
      inherit (live) pkgs config;
      kernel = config.boot.kernelPackages.kernel;
    in {
      overlays.default = import ./overlay.nix;
      nixosModules.surface-pro-11 = ./modules/denali.nix;
      nixosModules.denali-uki = ./modules/denali-uki.nix;
      nixosConfigurations.denali-live = live;
      packages.${system} = {
        default = config.system.build.denaliIso;
        denali-live-iso = config.system.build.denaliIso;
        denali-live-iso-local = (mkLive true).config.system.build.denaliIso;
        denali-live-uki = config.system.build.uki;
      };
      checks.${system}.denali-hardware =
        assert !isolated.config.surface.devices.denali.enable;
        assert isolated.config.hardware.deviceTree.name == null;
        assert config.networking.wireless.enable && config.networking.wireless.dbusControlled;
        assert !config.services.openssh.enable;
        pkgs.runCommand "denali-hardware-check" { nativeBuildInputs = [ pkgs.dtc ]; } ''
          dtb=${kernel}/dtbs/${config.hardware.deviceTree.name}
          mods=${kernel.modules}/lib/modules/${kernel.modDirVersion}
          board=${pkgs.surfacePackages.wifiBoard}/lib/firmware/ath12k/WCN7850/hw2.0/board.bin
          fdtget -t s "$dtb" / compatible | grep -w microsoft,denali-oled
          for module in ath12k_wifi7 panel-samsung-atna33xc20 tcsrcc-x1e80100; do
            test -n "$(find "$mods" -name "$module.ko*" -print -quit)"
          done
          mkdir -p "$out"
          sha256sum "$dtb" "$board" > "$out/sha256sums"
        '';
    };
}
