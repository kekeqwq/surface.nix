{
  description = "Opt-in NixOS hardware support for Surface Pro 11 Denali OLED";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable-small";
  # Keep the validated kernel compiler, module tools and DTB filter independent
  # of the host userspace. Replace only with a verified native boot baseline.
  inputs.daily-kernel-nixpkgs.url = "github:NixOS/nixpkgs/52a93865f031ba894c0d19121dda6b75c0f2b2b8";

  outputs =
    { nixpkgs, daily-kernel-nixpkgs, ... }:
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
      fullioPackages = pkgs: rec {
        kernel = pkgs.surfacePackages.surfaceNext;
        fullio-reference-topology = pkgs.callPackage ./pkgs/fullio-topology.nix { };
        fullio-reference-volume = pkgs.callPackage ./pkgs/fullio-reference-volume.nix { };
        fullio-checked-capture-kernel = kernel.override {
          shortRelease = true;
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
                  # Checked capture depends on the FullIO changes above.
                  ./pkgs/patches/sp11-fullio-capture-read-order.patch
                  ./pkgs/patches/sp11-fullio-capture-read-prefix.patch
                  ./pkgs/patches/sp11-fullio-checked-capture.patch
                  ./pkgs/patches/sp11-fullio-capture-early-drain.patch
                ];
        };
      };
      packages = (removeAttrs (fullioPackages pkgs) [ "kernel" ]) // {
        default = kernel;
        surface-live-iso = live.config.system.build.surfaceLiveIso;
      };
      dailyPkgs = import daily-kernel-nixpkgs {
        inherit system;
        overlays = [ overlay ];
      };
      dailyPackages = fullioPackages dailyPkgs;
      dailySystem = daily-kernel-nixpkgs.lib.nixosSystem {
        modules = [
          ./modules/denali.nix
          (import ./modules/denali/fullio-reference-render.nix dailyPackages)
          (import ./modules/denali/fullio-reference-clock-audit.nix dailyPackages)
          {
            nixpkgs.hostPlatform = system;
            system.stateVersion = "26.05";
            surface.devices.denali = {
              enable = true;
              keyboard.hhkb.enable = true;
            };
          }
        ];
      };
      dailyBoot = dailySystem.config;
      dailyKernel = dailyBoot.boot.kernelPackages.kernel;
      fsgenOrderKernel = dailyKernel.override {
        kernelPatches = dailyKernel.kernelPatches ++ [
          {
            name = "denali-lpass-fsgen-pm-order";
            patch = ./pkgs/patches/denali-lpass-fsgen-pm-order.patch;
          }
        ];
      };
      fsgenOrderPackages = dailyPkgs.linuxPackagesFor fsgenOrderKernel;
      # Unqualified upstream review snapshot. Intentionally no NixOS module or host selector.
      gmuBindingBuildOnlyKernel = fsgenOrderKernel.override {
        kernelPatches = fsgenOrderKernel.kernelPatches ++ [
          {
            name = "denali-adreno-gmu-driver-v2-build-only";
            patch = ./pkgs/patches/denali-adreno-gmu-driver-v2-build-only.patch;
          }
          {
            name = "denali-adreno-gmu-balance-failed-bind-rpm";
            patch = ./pkgs/patches/denali-adreno-gmu-balance-failed-bind-rpm.patch;
          }
        ];
      };
      fsgenOrderExperiment = import ./modules/denali/fsgen-order-experiment.nix {
        kernelPackages = fsgenOrderPackages;
      };
      mkTouchModule =
        kernelPackages:
        kernelPackages.callPackage ./pkgs/denali-module-candidate.nix {
          repo = "SP11X1e-touchscreen";
          rev = "1cb0ce2b3cc95821433410081b6cbba634eddc41";
          hash = "sha256-5kmgoD1n1AVCr2vt1oBsDsFkOf552lnyLU8h9/Alz5A=";
          subdir = "production-v1";
          module = "mshw0485_touch";
          patches = [
            ./pkgs/patches/denali-mshw0485-regulator.patch
            ./pkgs/patches/denali-mshw0485-next24-transport.patch
          ];
        };
      touchModule = mkTouchModule dailyBoot.boot.kernelPackages;
      orderedTouchModule = mkTouchModule fsgenOrderPackages;
      touchDtbs = pkgs.callPackage ./pkgs/denali-touch-dtb-candidate.nix {
        dtbs = dailyBoot.hardware.deviceTree.package;
      };
      nativeTouch = import ./modules/denali/native-touch.nix {
        inherit touchModule touchDtbs;
        kernel = dailyKernel;
        additionalVariants = [
          {
            kernel = fsgenOrderKernel;
            touchModule = orderedTouchModule;
          }
        ];
      };
      mkQceDtbs = pkgs.callPackage ./pkgs/denali-qce-disabled-dtb-candidate.nix;
      stockQceDtbs = mkQceDtbs { dtbs = dailyBoot.hardware.deviceTree.package; };
      nativeQceDtbs = mkQceDtbs {
        dtbs = touchDtbs;
        touchCompatible = "microsoft,mshw0485";
      };
      nativeQceIceDtbs = pkgs.callPackage ./pkgs/denali-ice-disabled-dtb-candidate.nix {
        dtbs = nativeQceDtbs;
      };
      nativeQceIceThermalDtbs = pkgs.callPackage ./pkgs/denali-cpu-thermal-guard-dtb.nix {
        dtbs = nativeQceIceDtbs;
      };
      qceExperiment = import ./modules/denali/qce-experiment.nix {
        inherit stockQceDtbs nativeQceDtbs nativeQceIceDtbs nativeQceIceThermalDtbs;
        kernel = dailyKernel;
        additionalKernels = [ fsgenOrderKernel ];
      };
      evaluateDaily =
        enable: disableUnusedQce: orderFsgenResume: disableUnusedUfsIce: cpuThermalGuard:
        (dailySystem.extendModules {
          modules = [
            nativeTouch
            qceExperiment
            fsgenOrderExperiment
            {
              surface.devices.denali = {
                touchscreen.native = { inherit enable; };
                power = { inherit disableUnusedQce orderFsgenResume disableUnusedUfsIce cpuThermalGuard; };
              };
            }
          ];
        }).config;
    in
    {
      # Hardware only: no historical users, authentication, mounts or desktop.
      denaliDailyBoot = {
        kernelPackages = dailyBoot.boot.kernelPackages;
        dtbs = dailyBoot.hardware.deviceTree.package;
      };
      overlays.default = overlay;
      nixosModules.default = ./modules/denali.nix;
      nixosModules.denali-native-touch = nativeTouch;
      nixosModules.denali-qce-experiment = {
        imports = [
          nativeTouch
          qceExperiment
        ];
      };
      nixosModules.denali-fsgen-order-experiment = fsgenOrderExperiment;
      # The installed host imports these layers in order so the existing
      # firmware manifest and initrd remain unchanged.
      nixosModules.fullio-reference-render = import ./modules/denali/fullio-reference-render.nix packages;
      nixosModules.fullio-reference-clock-audit = import ./modules/denali/fullio-reference-clock-audit.nix packages;
      nixosConfigurations.surface-live = live;
      packages.${system} = packages // {
        # Neither the installed host nor the Live image selects these by default.
        denali-touch-candidate = touchModule;
        denali-touch-dtb-candidate = touchDtbs;
        denali-qce-disabled-dtb-candidate = stockQceDtbs;
        denali-native-touch-qce-disabled-dtb-candidate = nativeQceDtbs;
        denali-unused-ufs-ice-disabled-dtb-candidate = nativeQceIceDtbs;
        denali-cpu-thermal-guard-dtb = nativeQceIceThermalDtbs;
        denali-lpass-fsgen-order-kernel-candidate = fsgenOrderKernel;
        denali-adreno-gmu-binding-build-only = gmuBindingBuildOnlyKernel;
        denali-adsp-pld-candidate =
          dailyBoot.boot.kernelPackages.callPackage ./pkgs/denali-module-candidate.nix
            {
              repo = "sp11-suspend-resume-public";
              rev = "0376e252eef2480dff550e1421e40e3e46ff9e02";
              hash = "sha256-aFPZfs6yu1SjEeZjQ83Cebz8FAkW9uy0DCHksOFjNYQ=";
              subdir = "drivers/denali-adsp-pld-standby";
              module = "denali_adsp_pld_standby";
            };
      };
      checks.${system} = {
        denali-adreno-gmu-build-payload =
          let
            dtb = "qcom/x1e80100-microsoft-denali-oled.dtb";
            msmPath = "lib/modules/${gmuBindingBuildOnlyKernel.modDirVersion}/kernel/drivers/gpu/drm/msm";
          in
          pkgs.runCommand "denali-adreno-gmu-build-payload" { nativeBuildInputs = [ pkgs.kmod ]; } ''
            cmp ${fsgenOrderKernel}/dtbs/${dtb} ${gmuBindingBuildOnlyKernel}/dtbs/${dtb}
            set -- ${gmuBindingBuildOnlyKernel.modules}/${msmPath}/msm.ko*
            test "$#" = 1 && test -s "$1"
            modinfo -F alias "$1" > aliases
            grep -Fx 'of:N*T*Cqcom,adreno-gmu' aliases
            touch "$out"
          '';
        denali-native-touch-config =
          let
            stock = evaluateDaily false false false false false;
            native = evaluateDaily true false false false false;
            stockQce = evaluateDaily false true false false false;
            nativeQce = evaluateDaily true true false false false;
            ordered = evaluateDaily true true true false false;
            orderedIce = evaluateDaily true true true true false;
            guarded = evaluateDaily true true true true true;
            moduleInstalled =
              cfg: builtins.any (p: p.drvPath == touchModule.drvPath) cfg.boot.extraModulePackages;
          in
          assert stock.services.iptsd.enable && stock.systemd.services ? denali-iptsd;
          assert stock.hardware.deviceTree.package.drvPath == dailyBoot.hardware.deviceTree.package.drvPath;
          assert !moduleInstalled stock;
          assert !native.services.iptsd.enable && !(native.systemd.services ? denali-iptsd);
          assert native.hardware.deviceTree.package.drvPath == touchDtbs.drvPath;
          assert moduleInstalled native;
          assert native.boot.kernelPackages.kernel.drvPath == stock.boot.kernelPackages.kernel.drvPath;
          assert !(builtins.elem "mshw0485_touch" native.boot.kernelModules);
          assert stockQce.hardware.deviceTree.package.drvPath == stockQceDtbs.drvPath;
          assert nativeQce.hardware.deviceTree.package.drvPath == nativeQceDtbs.drvPath;
          assert stockQce.services.iptsd.enable && !moduleInstalled stockQce;
          assert !nativeQce.services.iptsd.enable && moduleInstalled nativeQce;
          assert nativeQce.boot.kernelPackages.kernel.drvPath == native.boot.kernelPackages.kernel.drvPath;
          assert ordered.boot.kernelPackages.kernel.drvPath == fsgenOrderKernel.drvPath;
          assert ordered.hardware.deviceTree.package.drvPath == nativeQceDtbs.drvPath;
          assert orderedIce.hardware.deviceTree.package.drvPath == nativeQceIceDtbs.drvPath;
          assert orderedIce.boot.kernelPackages.kernel.drvPath == ordered.boot.kernelPackages.kernel.drvPath;
          assert orderedIce.boot.extraModulePackages == ordered.boot.extraModulePackages;
          assert guarded.hardware.deviceTree.package.drvPath == nativeQceIceThermalDtbs.drvPath;
          assert guarded.boot.kernelPackages.kernel.drvPath == orderedIce.boot.kernelPackages.kernel.drvPath;
          assert guarded.boot.extraModulePackages == orderedIce.boot.extraModulePackages;
          assert !ordered.services.iptsd.enable && !moduleInstalled ordered;
          assert builtins.any (p: p.drvPath == orderedTouchModule.drvPath) ordered.boot.extraModulePackages;
          pkgs.runCommand "denali-native-touch-config" { } ''
            tree=${native.system.modulesTree}/lib/modules/${native.boot.kernelPackages.kernel.modDirVersion}
            test -s "$tree/modules.cer"
            test -s "$tree/updates/mshw0485_touch.ko.cer"
            grep -q 'microsoft,mshw0485.*mshw0485_touch$' "$tree/modules.alias"
            touch "$out"
          '';
        denali-fsgen-order-payload =
          let
            dtb = "qcom/x1e80100-microsoft-denali-oled.dtb";
            ordered = evaluateDaily true true true false false;
          in
          pkgs.runCommand "denali-fsgen-order-payload" { } ''
            cmp ${dailyKernel}/dtbs/${dtb} ${fsgenOrderKernel}/dtbs/${dtb}
            tree=${ordered.system.modulesTree}/lib/modules/${fsgenOrderKernel.modDirVersion}
            test -s "$tree/updates/mshw0485_touch.ko.cer"
            grep -q 'microsoft,mshw0485.*mshw0485_touch$' "$tree/modules.alias"
            touch "$out"
          '';
        surface-live-config =
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
      };
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
