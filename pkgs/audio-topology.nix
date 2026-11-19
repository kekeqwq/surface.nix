{ stdenv, fetchurl, cmake, m4, alsa-utils, lib }:
stdenv.mkDerivation {
  pname = "denali-audioreach-topology";
  version = "2026-09-18";
  src = fetchurl {
    url = "https://github.com/linux-msm/audioreach-topology/archive/993a17dcb672357998a463a73f120064d6c74f4f.tar.gz";
    sha256 = "58e0fa0ab9702c5237b4bea1f0486bcc8af7470fafd2d4ad8d508754fd269b17";
  };
  nativeBuildInputs = [ cmake m4 alsa-utils ];
  buildPhase = ''
    runHook preBuild
    cmake --build . --target topology_X1E80100-Microsoft-Surface-Pro-11
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm644 qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin \
      "$out/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin"
    runHook postInstall
  '';
  meta.license = lib.licenses.bsd3;
}
