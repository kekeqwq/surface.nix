{
  linuxManualConfig,
  fetchurl,
  kernelPatches ? [ ],
  # CONFIG_EFI_STUB=y. NixOS systemd-boot checks this attribute, not the Kconfig.
  features ? {
    efiBootStub = true;
  },
  randstructSeed ? "",
  configfile ? ./config-denali-next.aarch64,
  localVersion ? "-surface-touch",
}:
linuxManualConfig {
  pname = "surface-next";
  version = "7.4.0-rc3-next-20261119";
  modDirVersion = "7.4.0-rc3-next-20261119${localVersion}";
  extraMakeFlags = if localVersion == "" then [ ] else [ "LOCALVERSION=${localVersion}" ];
  # kernel.org next-20261119, peeled commit adcad7f4e6332cff3d6d7165f41584899f598534.
  src = fetchurl {
    name = "linux-next-20261119.tar.gz";
    url = "https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git/snapshot/linux-next-next-20261119.tar.gz";
    hash = "sha256-7LzID31shRxxdS+OrqbLQOvzv0yGi9fVK7aWY1XViMc=";
  };
  # One audited Denali configuration and its dependency-ordered touch queue.
  # No alternate downstream kernel, graphics workaround or register experiment.
  inherit
    configfile
    kernelPatches
    features
    randstructSeed
    ;
  allowImportFromDerivation = true;
}
