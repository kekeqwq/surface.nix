# Text-only Surface installer. It does not change a running installation.
#
# Boot through the same aligned zboot UKI used by the installed system. A raw
# Image fails in the EFI stub with a 64 KiB alignment error on this firmware.
# The UKI contains no private GPU/audio firmware; those files stay off Git and
# out of this public image.
{
  config,
  lib,
  pkgs,
  modulesPath,
  ...
}:
let
  # Keep install-media filesystems out of the ordinary Denali kernel.
  baseConfig = builtins.readFile ../pkgs/config-denali-next.aarch64;
  liveConfig = pkgs.writeText "denali-live.config" (
    lib.replaceStrings
      [ "# CONFIG_ISO9660_FS is not set" "# CONFIG_SQUASHFS is not set" ]
      [ "CONFIG_ISO9660_FS=m" "CONFIG_SQUASHFS=m\nCONFIG_SQUASHFS_ZSTD=y" ]
      baseConfig
  );
  liveKernel = pkgs.surfacePackages.surfaceNext.override {
    configfile = liveConfig;
    localVersion = "-surface-live";
  };
  isoInspector = pkgs.runCommand "surface-live-inspector" { } ''
    mkdir -p "$out"
    cp ${../scripts/inspect-live-iso.py} "$out/inspect-live-iso.py"
    cp ${../scripts/inspect-efi-payload.py} "$out/inspect-efi-payload.py"
  '';
  efi = config.boot.uki.settings.UKI;
  ukiFile = "surface-live.efi";
  cmdline = "init=${config.system.build.toplevel}/init ${toString config.boot.kernelParams}";
  uki =
    pkgs.runCommand "surface-live-uki"
      {
        nativeBuildInputs = [
          pkgs.systemdUkify
          pkgs.python3
          pkgs.zstd
        ];
      }
      ''
        ukify build \
          --linux ${efi.Linux} \
          --initrd ${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile} \
          --devicetree ${efi.DeviceTree} \
          --cmdline ${lib.escapeShellArg cmdline} \
          --stub ${config.systemd.package}/lib/systemd/boot/efi/linuxaa64.efi.stub \
          --os-release @${config.system.build.toplevel}/etc/os-release \
          --uname ${lib.escapeShellArg efi.Uname} \
          --output "$out"
        python3 ${../scripts/inspect-efi-payload.py} "$out" \
          --expect-uki ${lib.escapeShellArg efi.Uname} \
          --expect-linux ${efi.Linux} \
          --expect-dtb ${efi.DeviceTree} \
          --expect-initrd ${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile} \
          --expect-cmdline ${lib.escapeShellArg cmdline}
      '';
  loader = "${config.systemd.package}/lib/systemd/boot/efi/systemd-bootaa64.efi";
  loaderConf = pkgs.writeText "loader.conf" ''
    default ${ukiFile}
    timeout 5
    editor no
  '';
  esp =
    pkgs.runCommand "surface-live-esp.img"
      {
        nativeBuildInputs = [
          pkgs.dosfstools
          pkgs.libfaketime
          pkgs.mtools
        ];
      }
      ''
        truncate -s "$(( $(stat -c %s ${uki}) + 96 * 1024 * 1024 ))" "$out"
        mkfs.vfat --invariant -F 32 -n SURFACE "$out"
        export TZ=UTC
        fat() { faketime -f '2000-01-01 00:00:00' "$@"; }
        fat mmd -i "$out" ::EFI ::EFI/BOOT ::EFI/Linux ::loader
        fat mcopy -i "$out" ${loader} ::EFI/BOOT/BOOTAA64.EFI
        fat mcopy -i "$out" ${uki} ::EFI/Linux/${ukiFile}
        fat mcopy -i "$out" ${loaderConf} ::loader/loader.conf
        mcopy -i "$out" ::EFI/Linux/${ukiFile} embedded.efi
        cmp ${uki} embedded.efi
      '';
  image = pkgs.callPackage (modulesPath + "/../lib/make-iso9660-image.nix") {
    isoName = "nixos-surface-live-aarch64.iso";
    inherit (config.isoImage) volumeID squashfsCompression contents;
    squashfsContents = config.isoImage.storeContents;
    syslinux = null;
    efiBootable = true;
    efiBootImage = "boot/efi.img";
  };
in
{
  imports = [
    ../modules/denali.nix
    (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix")
  ];

  nixpkgs.hostPlatform = "aarch64-linux";
  surface.devices.denali.enable = true;
  hardware.enableAllHardware = lib.mkForce false;
  networking.hostName = "surface-live";
  # A new, stateless Live environment; not the installed host's compatibility baseline.
  system.stateVersion = "26.11";
  networking.networkmanager.enable = true;
  networking.wireless.enable = lib.mkForce false;
  documentation.enable = false;
  documentation.man.enable = false;
  documentation.doc.enable = false;
  boot.loader.grub.memtest86.enable = lib.mkForce false;

  # The installed host remains ext4. The installer itself must be able to
  # create the secret-lab layout: LUKS2 plus compressed Btrfs.
  boot.kernelPackages = lib.mkForce (pkgs.linuxPackagesFor liveKernel);
  boot.swraid.enable = lib.mkForce false;
  boot.initrd.services.lvm.enable = lib.mkForce false;
  boot.supportedFilesystems = lib.mkForce [
    "btrfs"
    "ext4"
    "vfat"
  ];
  boot.initrd.supportedFilesystems = lib.mkForce [
    "iso9660"
    "squashfs"
    "overlay"
  ];
  boot.initrd.availableKernelModules = {
    iso9660 = true;
    squashfs = true;
    overlay = true;
    loop = true;
  };
  boot.kernelParams = [
    "fbcon=font:TER16x32"
    "console=tty0"
  ];
  console.font = "ter-v32n";
  console.packages = [ pkgs.terminus_font ];
  services.getty.autologinUser = lib.mkForce "root";

  # Public installer access. Anyone who can reach this SSH port becomes root.
  # Do not boot this image on an untrusted network.
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "yes";
      PasswordAuthentication = true;
      KbdInteractiveAuthentication = false;
      PermitEmptyPasswords = true;
    };
  };
  security.pam.services.sshd.allowNullPassword = true;
  users.mutableUsers = true;
  users.users.root.initialHashedPassword = lib.mkForce null;
  users.users.root.password = lib.mkForce "";
  networking.firewall.allowedTCPPorts = [ 22 ];

  programs.git.enable = true;
  environment.systemPackages = with pkgs; [
    git
    util-linux
    gptfdisk
    dosfstools
    btrfs-progs
    cryptsetup
    libfido2
    python3
    iw
    usbutils
  ];

  isoImage = {
    edition = "surface-live";
    volumeID = "SURFACE_LIVE";
    makeBiosBootable = false;
    makeUsbBootable = false;
    makeEfiBootable = lib.mkForce true;
    grubTheme = null;
    showConfiguration = false;
  };

  system.build.surfaceLiveIso = image.overrideAttrs (old: {
    nativeBuildInputs = old.nativeBuildInputs ++ [
      pkgs.libarchive
      pkgs.mtools
      pkgs.python3
    ];
    buildCommandPath = pkgs.writeText "make-surface-live-iso.sh" (
      lib.replaceStrings
        [ "-e $efiBootImage" "-isohybrid-gpt-basdat" ]
        [
          "-e --interval:appended_partition_2:all::"
          "-partition_offset 16 -append_partition 2 C12A7328-F81F-11D2-BA4B-00A0C93EC93B ${esp} -appended_part_as_gpt"
        ]
        (builtins.readFile old.buildCommandPath)
      + ''
        python3 ${isoInspector}/inspect-live-iso.py nixos-uki "$out/iso/$isoName"
      ''
    );
  });
}
