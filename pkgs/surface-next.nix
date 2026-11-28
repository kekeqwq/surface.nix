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
  shortRelease ? false,
}:
let
  tag = "next-20261124";
  tagObject = "ecfab21e114b19a8425356b5b7547c471bd6ebb2";
  commit = "3dd8c790a7b7027abdd568e36db5e82ffaea7c77";
  upstreamVersion = "7.4.0-rc4";
  version = "${upstreamVersion}-${tag}";
  # NixOS passes this release explicitly to depmod, which requires a numeric
  # major.minor prefix. Keep the RC version as well, without the FullIO suffix.
  release = "${upstreamVersion}-surface-${tag}";
in
linuxManualConfig {
  pname = "surface-next";
  inherit version;
  # Keep the numeric upstream version for Nixpkgs' feature checks. Kbuild
  # uses KERNELRELEASE for uname and module vermagic/paths; rebuildImage
  # inherits these same make flags for the zboot image.
  modDirVersion = if shortRelease then release else "${version}${localVersion}";
  extraMakeFlags =
    if shortRelease then
      [ "KERNELRELEASE=${release}" ]
    else if localVersion == "" then
      [ ]
    else
      [ "LOCALVERSION=${localVersion}" ];
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
    hash = "sha256-1NXXoLsXnVT2yu9PvWe9zec5hZeJUo/rtrB9UQW63Qs=";
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
