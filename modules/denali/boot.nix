{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.surface.devices.denali;
  loader = config.boot.loader;
  bootMount =
    if loader.systemd-boot.xbootldrMountPoint == null then
      loader.efi.efiSysMountPoint
    else
      loader.systemd-boot.xbootldrMountPoint;
  zboot = config.boot.kernelPackages.rebuildImage { target = "vmlinuz.efi"; };
  linux = "${zboot}/vmlinuz.efi";
  kernel = config.boot.kernelPackages.kernel;
  # These inputs do not depend on the toplevel. The final command line does,
  # so never link system.build.uki back into its own system closure.
  components = pkgs.runCommand "denali-boot-components" { } ''
    mkdir -p "$out"
    ln -s ${linux} "$out/linux"
    ln -s ${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile} "$out/initrd"
    ln -s ${config.hardware.deviceTree.package}/${config.hardware.deviceTree.name} "$out/dtb"
    ln -s ${config.systemd.package}/lib/systemd/boot/efi/linuxaa64.efi.stub "$out/stub"
    printf '%s\n' ${lib.escapeShellArg kernel.modDirVersion} > "$out/uname"
  '';
  install = pkgs.writeShellScript "surface-install-ukis" ''
    export PATH=${
      lib.makeBinPath [
        pkgs.coreutils
        pkgs.cpio
        pkgs.zstd
        pkgs.util-linux
        config.systemd.package
        pkgs.python3
      ]
    }
    export SURFACE_UKIFY=${pkgs.systemdUkify}/lib/systemd/ukify
    exec python3 ${../../scripts/install-ukis.py} ${../../scripts/inspect-efi-payload.py} "$@"
  '';
in
{
  options.surface.devices.denali.boot = {
    earlyDisplay = lib.mkEnableOption ''
      native OLED modesetting in the initrd (for example, for an encrypted root)
    '';
    earlyBrightnessPercent = lib.mkOption {
      type = lib.types.nullOr (lib.types.ints.between 1 100);
      default = null;
      description = ''
        Initial brightness of the Denali OLED's 12-bit eDP backlight in the
        initrd. Null preserves its power-on brightness. Does not change the
        desktop brightness saved and restored by systemd-backlight.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    boot.initrd.kernelModules = [ "simpledrm" ] ++ lib.optionals cfg.boot.earlyDisplay [
      "dispcc-x1e80100"
      "gpucc-x1e80100"
      # MDSS waits for both USB-C DP components even when using only eDP.
      "qcom_glink_smem"
      "qrtr"
      "pmic_glink"
      "pmic_glink_altmode"
      "ps883x"
    ];
    # PMIC GLINK initializes PDR/QMI over AF_QIPCRTR. This is a socket
    # dependency, not a kmod symbol dependency; kernelModules is sorted.
    boot.initrd.systemd.contents = lib.mkIf cfg.boot.earlyDisplay {
      "/etc/modprobe.d/denali-display.conf".text = ''
        softdep pmic_glink pre: qrtr
      '';
    };
    boot.initrd.services.udev.rules = lib.mkIf (cfg.boot.earlyDisplay && cfg.boot.earlyBrightnessPercent != null) ''
      ACTION=="add", SUBSYSTEM=="backlight", KERNEL=="dp_aux_backlight", KERNELS=="aea0000.displayport-controller", ATTR{max_brightness}=="4095", ATTR{brightness}="${toString (builtins.div (4095 * cfg.boot.earlyBrightnessPercent + 50) 100)}"
    '';
    boot.kernelParams = [
      "arm64.nopauth"
      "systemd.mask=tpm2.target"
      "systemd.tpm2_wait=0"
    ]
    ++ lib.optional (cfg.privateFirmwareDirectory != null) "firmware_class.path=/surface-firmware";
    boot.uki.settings.UKI = {
      Linux = linux;
      HWIDs = "";
    };
    system.systemBuilderCommands = ''
      ln -s ${components} "$out/surface-boot"
    '';
    boot.loader.systemd-boot = {
      configurationLimit = lib.mkDefault 5;
      extraInstallCommands = lib.mkAfter ''
        ${install} ${lib.escapeShellArg bootMount} "$1" ${
          lib.escapeShellArg (
            if cfg.privateFirmwareDirectory == null then "" else cfg.privateFirmwareDirectory
          )
        }
      '';
    };
    boot.loader.timeout = lib.mkDefault 5;
  };
}
