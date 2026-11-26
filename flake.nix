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
      live = nixpkgs.lib.nixosSystem {
        modules = [ ./live/default.nix ];
      };
      packages = rec {
        default = kernel;
        surface-live-iso = live.config.system.build.surfaceLiveIso;
        fullio-reference-topology = pkgs.callPackage ./pkgs/fullio-topology.nix { };
        fullio-reference-volume = pkgs.callPackage ./pkgs/fullio-reference-volume.nix { };
        fullio-reference-kernel = kernel.override {
          localVersion = "-surface-fullio";
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
                  ./pkgs/patches/denali-fullio-pa-cache.patch
                  ./pkgs/patches/fullio/audioreach-fullio.patch
                  ./pkgs/patches/fullio/asoc-denali-routing.patch
                  # Context depends on the FullIO q6apm/q6apm-dai/q6apm.h
                  # additions above: keep this after the common FullIO patches.
                  ./pkgs/patches/denali-fullio-gain-snapshot.patch
                ];
        };
        fullio-checked-capture-kernel = fullio-reference-kernel.override {
          localVersion = "-surface-fullio-checked-capture";
          kernelPatches =
            # Keep the tested checked-capture v2 kernel byte-identical:
            # the separate gain snapshot diagnostic is not part of v2.
            builtins.filter (p: (p.name or "") != "denali-fullio-gain-snapshot.patch")
              fullio-reference-kernel.kernelPatches
            ++
              map
                (patch: {
                  name = builtins.baseNameOf patch;
                  inherit patch;
                })
                [
                  ./pkgs/patches/sp11-fullio-capture-read-order.patch
                  ./pkgs/patches/sp11-fullio-capture-read-prefix.patch
                  ./pkgs/patches/sp11-fullio-checked-capture.patch
                  ./pkgs/patches/sp11-fullio-capture-early-drain.patch
                ];
        };
      };
    in
    {
      overlays.default = overlay;
      nixosModules.default = ./modules/denali.nix;
      nixosModules.fullio-reference-render = import ./modules/denali/fullio-reference-render.nix packages;
      nixosModules.fullio-reference-clock-audit = import ./modules/denali/fullio-reference-clock-audit.nix packages;
      nixosConfigurations.surface-live = live;
      packages.${system} = packages;
      checks.${system}.surface-live-config =
        pkgs.runCommand "surface-live-config"
          {
            contract = builtins.toJSON {
              networkmanager = live.config.networking.networkmanager.enable;
              wifiBackend = live.config.networking.networkmanager.wifi.backend;
              wifiEnabled = live.config.networking.wireless.enable;
              wifiDbus = live.config.networking.wireless.dbusControlled;
              wifiUnit = live.config.systemd.services.wpa_supplicant.enable;
              ssh = live.config.services.openssh.enable;
              root = live.config.services.openssh.settings.PermitRootLogin;
              empty = live.config.services.openssh.settings.PermitEmptyPasswords;
              cmdline = live.config.boot.kernelParams;
              hhkb = live.config.surface.devices.denali.keyboard.hhkb.enable;
              kernelPatches = map (patch: patch.name) live.config.boot.kernelPackages.kernel.kernelPatches;
              media = live.config.fileSystems."/iso".device;
              squashfsOptions = live.config.fileSystems."/nix/.ro-store".options;
              tools = map (pkg: pkg.pname or pkg.name) live.config.environment.systemPackages;
            };
          }
          ''
            printf '%s\n' "$contract" > "$out"
            grep -q '"networkmanager":true' "$out"
            grep -Fq '"wifiBackend":"wpa_supplicant"' "$out"
            grep -Fq '"wifiEnabled":true' "$out"
            grep -Fq '"wifiDbus":true' "$out"
            grep -Fq '"wifiUnit":true' "$out"
            grep -q '"ssh":true' "$out"
            grep -q '"root":"yes"' "$out"
            grep -q '"empty":true' "$out"
            grep -Fq 'fbcon=font:TER16x32,nodefer' "$out"
            grep -Fq 'rd.systemd.show_status=yes' "$out"
            grep -Fq '"hhkb":true' "$out"
            grep -Fq '"denali-hhkb"' "$out"
            grep -Fq '"surface_hid_core.denali_hhkb=1"' "$out"
            grep -Fq '"media":"/dev/disk/by-label/SURFACE_LIVE"' "$out"
            grep -Fq '"squashfsOptions":["x-initrd.mount","loop"]' "$out"
            for tool in git util-linux gptfdisk dosfstools btrfs-progs cryptsetup libfido2 python3 iw usbutils; do
              grep -q "\"$tool\"" "$out"
            done
          '';
      devShells = nixpkgs.lib.genAttrs [ system "aarch64-darwin" "x86_64-linux" ] (
        toolSystem:
        let
          tools = nixpkgs.legacyPackages.${toolSystem};
        in
        {
          surface-live = tools.mkShellNoCC {
            packages = with tools; [
              python3
              msitools
              xorriso
              mtools
              libarchive
              zstd
            ];
          };
        }
        // nixpkgs.lib.optionalAttrs (toolSystem == system) {
          surface-next = pkgs.mkShell {
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
        }
      );
    };
}
