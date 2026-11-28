{
  lib,
  stdenv,
  fetchFromGitHub,
  kernel,
  kernelModuleMakeFlags,
  repo,
  rev,
  hash,
  subdir,
  module,
  patches ? [ ],
}:
let
  kdir = "${kernel.dev}/lib/modules/${kernel.modDirVersion}/build";
  src = fetchFromGitHub {
    owner = "geocausa";
    inherit repo rev hash;
  };
in
stdenv.mkDerivation {
  pname = "${module}-candidate";
  version = builtins.substring 0 12 rev;
  inherit src patches;
  sourceRoot = "${src.name}/${subdir}";
  nativeBuildInputs = kernel.moduleBuildDependencies;
  enableParallelBuilding = true;
  dontConfigure = true;
  dontPatchELF = true; # A .ko is a relocatable ELF, not an executable.
  dontStrip = true; # Do not invalidate the signature written by Kbuild.
  # Call Kbuild directly. The upstream touch wrapper is restricted to the
  # author's unified13 release; this is only a compile check for our ABI.
  buildPhase = ''
    runHook preBuild
    make -C ${kdir} M="$PWD" W=1 -j"$NIX_BUILD_CORES" ${lib.escapeShellArgs kernelModuleMakeFlags} modules
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    # Let Kbuild sign and install the module and its .ko.cer sidecar;
    # NixOS's aggregateModules merges these into the boot trust material.
    make -C ${kdir} M="$PWD" INSTALL_MOD_PATH="$out" DEPMOD=true \
      ${lib.escapeShellArgs kernelModuleMakeFlags} modules_install
    rm -f "$out/lib/modules/${kernel.modDirVersion}/build" "$out/lib/modules/${kernel.modDirVersion}/source"
    find "$out/lib/modules/${kernel.modDirVersion}" -type f -name '${module}.ko.cer' -size +0c | grep -q .
    runHook postInstall
  '';
  meta = {
    description = "Build-only Denali candidate module; not enabled on the running system";
    homepage = "https://github.com/geocausa/${repo}";
    license = lib.licenses.gpl2Only;
    platforms = [ "aarch64-linux" ];
  };
}
