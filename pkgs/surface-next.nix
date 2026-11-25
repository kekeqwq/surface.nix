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
  version = "7.4.0-rc4-next-20261124";
  modDirVersion = "7.4.0-rc4-next-20261124${localVersion}";
  extraMakeFlags = if localVersion == "" then [ ] else [ "LOCALVERSION=${localVersion}" ];
  # kernel.org next-20261124 (ecfab21e114b19a8425356b5b7547c471bd6ebb2).
  src = fetchurl {
    name = "linux-next-20261124.tar.gz";
    url = "https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git/snapshot/linux-next-next-20261124.tar.gz";
    hash = "sha256-IbCXkkoBYMH/ZYsaaQfEE7Maih8VtNrOGW0G/NLMsjY=";
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
