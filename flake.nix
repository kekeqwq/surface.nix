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
    in
    {
      overlays.default = overlay;
      nixosModules.default = ./modules/denali.nix;
      packages.${system}.default = kernel;
      devShells.${system}.surface-next = pkgs.mkShell {
        inputsFrom = [ kernel ];
        nativeBuildInputs = [
          pkgs.util-linux
        ];
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
