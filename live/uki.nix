{
  config,
  lib,
  pkgs,
  modulesPath,
  ...
}:
let
  efi = config.boot.uki.settings.UKI;
  ukiFile = config.system.boot.loader.ukiFile;
  uki = "${config.system.build.uki}/${ukiFile}";
  loader = "${config.systemd.package}/lib/systemd/boot/efi/systemd-bootaa64.efi";
  loaderConf = pkgs.writeText "loader.conf" ''
    default ${ukiFile}
    timeout 5
    editor yes
  '';
  esp = pkgs.runCommand "denali-live-uki-esp.img" {
    nativeBuildInputs = [ pkgs.dosfstools pkgs.libfaketime pkgs.mtools pkgs.python3 ];
  } ''
    python3 ${../scripts/inspect-efi-payload.py} ${uki} \
      --expect-uki ${lib.escapeShellArg efi.Uname} \
      --expect-linux ${efi.Linux} --expect-dtb ${efi.DeviceTree} --expect-initrd ${efi.Initrd} \
      --expect-cmdline ${lib.escapeShellArg efi.Cmdline} > uki-contract.json
    truncate -s "$(( $(stat -c %s ${uki}) + 72 * 1024 * 1024 ))" "$out"
    mkfs.vfat --invariant -F 32 -n DENALI "$out"
    export TZ=UTC
    fat() { faketime -f '2000-01-01 00:00:00' "$@"; }
    fat mmd -i "$out" ::EFI ::EFI/BOOT ::EFI/Linux ::loader
    fat mcopy -i "$out" ${loader} ::EFI/BOOT/BOOTAA64.EFI
    fat mcopy -i "$out" ${uki} ::EFI/Linux/${ukiFile}
    fat mcopy -i "$out" ${loaderConf} ::loader/loader.conf
    fat mcopy -i "$out" uki-contract.json ::loader/uki-contract.json
    mcopy -i "$out" ::EFI/Linux/${ukiFile} embedded.efi
    cmp ${uki} embedded.efi
  '';
  image = pkgs.callPackage (modulesPath + "/../lib/make-iso9660-image.nix") {
    isoName = "nixos-denali-uki-${efi.Uname}-aarch64.iso";
    inherit (config.isoImage) volumeID squashfsCompression contents;
    squashfsContents = config.isoImage.storeContents;
    syslinux = null;
    efiBootable = true;
    efiBootImage = "boot/efi.img";
  };
in
{
  imports = [
    ../modules/denali-uki.nix
    (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix")
  ];

  surface.devices.denali.enable = true;
  # The stock installer requests drivers for unrelated boards that the pinned
  # SP11 kernel does not provide. Keep missing-module checks strict.
  hardware.enableAllHardware = lib.mkForce false;
  nixpkgs.hostPlatform = "aarch64-linux";
  system.stateVersion = "26.05";
  networking.hostName = "surface-live";
  # NetworkManager's default Wi-Fi backend enables a D-Bus-controlled
  # wpa_supplicant through networking.wireless; do not disable it here.
  networking.networkmanager.enable = true;
  environment.systemPackages = [ pkgs.iw ];
  documentation.enable = false;
  boot.supportedFilesystems = lib.mkForce [ "ext4" ];
  boot.initrd.supportedFilesystems = lib.mkForce [ "iso9660" "squashfs" "overlay" ];
  boot.uki = {
    name = "nixos-denali-oled";
    version = null;
  };
  services.openssh = {
    enable = lib.mkOverride 90 false;
    settings = {
      PermitRootLogin = "no";
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
    };
  };
  isoImage = {
    edition = "denali-uki";
    volumeID = "NIXOS_DENALI_UKI";
    makeBiosBootable = false;
    makeEfiBootable = lib.mkForce false;
    grubTheme = null;
    showConfiguration = false;
  };

  # The appended FAT partition is visible both as an El Torito EFI entry and
  # as a GPT ESP when the ISO is written directly to a USB device.
  system.build.denaliIso = image.overrideAttrs (old: {
    nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.libarchive pkgs.mtools pkgs.python3 ];
    buildCommandPath = pkgs.writeText "make-denali-uki-iso.sh" (
      lib.replaceStrings
        [ "-e $efiBootImage" "-isohybrid-gpt-basdat" ]
        [ "-e --interval:appended_partition_2:all::" "-partition_offset 16 -append_partition 2 C12A7328-F81F-11D2-BA4B-00A0C93EC93B ${esp} -appended_part_as_gpt" ]
        (builtins.readFile old.buildCommandPath)
      + ''
        python3 ${../scripts}/inspect-live-iso.py nixos-uki "$out/iso/$isoName" > "$out/boot-contract.json"
      ''
    );
  });
}
