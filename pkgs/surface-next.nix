{
  linuxManualConfig,
  fetchurl,
  kernelPatches ? [ ],
  features ? { },
  randstructSeed ? "",
  configfile ? ./config-sp11-7.3.aarch64,
  localVersion ? "",
}:
linuxManualConfig {
  pname = "surface-next";
  version = "7.4.0-rc3-next-20261118";
  modDirVersion = "7.4.0-rc3-next-20261118${localVersion}";
  extraMakeFlags = if localVersion == "" then [ ] else [ "LOCALVERSION=${localVersion}" ];
  # kernel.org next-20261118, peeled commit e8017d29067fd1310a65c3494ce1a1b492adbac6.
  src = fetchurl {
    name = "linux-next-20261118.tar.gz";
    url = "https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git/snapshot/linux-next-next-20261118.tar.gz";
    hash = "sha256-Rzq1yf8Frvq6hhR2SeetZeA2G8xuRqGhfOI61ATZLT4=";
  };
  # Start from the known-good Kconfig to isolate the source change. Do not
  # import the downstream patch queue or opt into downstream-only drivers.
  inherit configfile kernelPatches features randstructSeed;
  allowImportFromDerivation = true;
}
