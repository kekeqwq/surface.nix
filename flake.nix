{
  description = "Opt-in NixOS hardware support for Surface Pro 11 Denali OLED";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable-small";

  outputs =
    { nixpkgs, ... }:
    let
      system = "aarch64-linux";
      overlay = import ./overlay.nix;
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ overlay ];
      };
      kernel = pkgs.surfacePackages.surfaceNext;
      packages = {
        default = kernel;
        fullio-reference-topology = pkgs.callPackage ./pkgs/fullio-topology.nix { };
        fullio-reference-volume = pkgs.callPackage ./pkgs/fullio-reference-volume.nix { };
        fullio-reference-kernel = kernel.override {
          # Preserve the tested module ABI/release and private UKI gate.
          localVersion = "-surface-fullio-muted-test";
          kernelPatches =
            kernel.kernelPatches
            ++
              map
                (patch: {
                  name = builtins.baseNameOf patch;
                  inherit patch;
                })
                [
                  ./pkgs/patches/fullio/denali-device-tree.patch
                  ./pkgs/patches/fullio/soundwire-transport.patch
                  ./pkgs/patches/fullio/lpass-micarray.patch
                  ./pkgs/patches/fullio/wsa-speaker-protection.patch
                  ./pkgs/patches/fullio/audioreach-fullio.patch
                  ./pkgs/patches/fullio/asoc-denali-routing.patch
                ];
        };
      };
    in
    {
      overlays.default = overlay;
      nixosModules.default = ./modules/denali.nix;
      nixosModules.fullio-reference-render = import ./modules/denali/fullio-reference-render.nix packages;
      packages.${system} = packages;
      devShells.${system}.surface-next = pkgs.mkShell {
        inputsFrom = [ kernel ];
        nativeBuildInputs = [ pkgs.util-linux ];
        SURFACE_NEXT_SOURCE = kernel.src;
        SURFACE_NEXT_CONFIG = kernel.configfile;
        SURFACE_NEXT_RELEASE = kernel.modDirVersion;
        SURFACE_NEXT_LOCALVERSION = "-surface-touch";
        SURFACE_NEXT_PATCHES = nixpkgs.lib.concatMapStringsSep " " (
          p: toString p.patch
        ) kernel.kernelPatches;
        inherit (kernel.env) RUST_LIB_SRC;
      };
    };
}
