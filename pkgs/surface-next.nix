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
  version = "7.4.0-rc3-next-20261120";
  modDirVersion = "7.4.0-rc3-next-20261120${localVersion}";
  extraMakeFlags = if localVersion == "" then [ ] else [ "LOCALVERSION=${localVersion}" ];
  # kernel.org next-20261120.
  src = fetchurl {
    name = "linux-next-20261120.tar.gz";
    url = "https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git/snapshot/linux-next-next-20261120.tar.gz";
    hash = "sha256-cVoNFec2qmkHpVz8rTe4AgFl9ivdTRKTV+tej0nKct8=";
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
