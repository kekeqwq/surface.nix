{
  linuxManualConfig,
  fetchurl,
  kernelPatches ? [ ],
  features ? { },
  randstructSeed ? "",
}:
let
  # Source and base config from dwhinham/archlinux-repo at 94d875e2dec4.
  rev = "46bb6beace94874a3ec602bfb83e6f87995bc5d0";
  configfile = builtins.toFile "sp11-7.3.config" (
    # Match the PKGBUILD's scripts/config additions before olddefconfig.
    builtins.readFile ./config-sp11-7.3.aarch64 + "\nCONFIG_SPI_HID=m\nCONFIG_SPI_HID_OF=m\n"
  );
in
linuxManualConfig {
  pname = "linux-sp11";
  version = "7.3.4";
  modDirVersion = "7.3.4-arch1-1-sp11";
  extraMakeFlags = [ "LOCALVERSION=-1-sp11" ];
  src = fetchurl {
    name = "linux-sp11-${rev}.tar.gz";
    url = "https://codeload.github.com/dwhinham/linux-sp11/tar.gz/${rev}";
    hash = "sha256-Cryyfye6PonnPaxzDjNolXGhMqn0fOX8LzZfCKzFYMw=";
  };
  inherit configfile kernelPatches features randstructSeed;
  allowImportFromDerivation = true;
}
