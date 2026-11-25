{
  linuxManualConfig,
  fetchgit,
  kernelPatches ? [ ],
  # CONFIG_EFI_STUB=y. NixOS systemd-boot checks this attribute, not the Kconfig.
  features ? {
    efiBootStub = true;
  },
  randstructSeed ? "",
  configfile ? ./config-denali-next.aarch64,
  localVersion ? "-surface-touch",
}:
let
  tag = "next-20261124";
  tagObject = "ecfab21e114b19a8425356b5b7547c471bd6ebb2";
  commit = "3dd8c790a7b7027abdd568e36db5e82ffaea7c77";
  version = "7.4.0-rc4-${tag}";
in
linuxManualConfig {
  pname = "surface-next";
  inherit version;
  modDirVersion = "${version}${localVersion}";
  extraMakeFlags = if localVersion == "" then [ ] else [ "LOCALVERSION=${localVersion}" ];
  src = fetchgit {
    name = "linux-${tag}-source";
    url = "https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git";
    inherit tag;
    fetchSubmodules = false;
    # Verify both identities before fetchgit strips the Git metadata.
    postCheckout = ''
      test "$(git -C "$out" rev-parse refs/tags/${tag})" = ${tagObject}
      test "$(git -C "$out" rev-parse HEAD)" = ${commit}
    '';
    hash = "sha256-AoeKCkZJxmGJdBx7yBirtCIXNL5qikdWa2drZAwYYEU=";
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
