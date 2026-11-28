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
  # Call Kbuild directly. The upstream touch wrapper is restricted to the
  # author's unified13 release; this is only a compile check for our ABI.
  buildPhase = ''
    runHook preBuild
    make -C ${kdir} M="$PWD" W=1 -j"$NIX_BUILD_CORES" ${lib.escapeShellArgs kernelModuleMakeFlags} modules
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm644 ${module}.ko "$out/lib/modules/${kernel.modDirVersion}/extra/${module}.ko"
    runHook postInstall
  '';
  meta = {
    description = "Build-only Denali candidate module; not enabled on the running system";
    homepage = "https://github.com/geocausa/${repo}";
    license = lib.licenses.gpl2Only;
    platforms = [ "aarch64-linux" ];
  };
}
