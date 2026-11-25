{
  stdenvNoCC,
  fetchurl,
  alsa-utils,
  python3,
}:
stdenvNoCC.mkDerivation {
  pname = "sp11-fullio-v19c-reference-topology";
  version = "3232e1d";
  src = fetchurl {
    url = "https://raw.githubusercontent.com/geocausa/SP11X1e-audio/3232e1dacdeb580a10a9cb8d4756a4518a7bd83e/deploy/native-audio-v19c/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0.conf";
    sha256 = "241f32cd2278c7df745f17a6c70f3259109b68ffeea1d4984353de4afd99bc39";
  };
  dontUnpack = true;
  dontConfigure = true;
  nativeBuildInputs = [
    alsa-utils
    python3
  ];
  buildPhase = ''
    runHook preBuild
    alsatplg -c "$src" -o fullio-v19c.bin
    echo 'e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0  fullio-v19c.bin' | sha256sum -c -
    python3 ${../tests/fullio-topology.py} fullio-v19c.bin --self-test
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm644 fullio-v19c.bin "$out/share/sp11-fullio/v19c.bin"
    runHook postInstall
  '';
}
