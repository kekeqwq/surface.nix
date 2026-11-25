{
  stdenvNoCC,
  fetchurl,
  alsa-utils,
  python3,
  feedbackProbes ? false,
}:
stdenvNoCC.mkDerivation {
  pname =
    if feedbackProbes then
      "sp11-fullio-feedback-probe-topologies"
    else
      "sp11-fullio-v19c-reference-topology";
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
  buildPhase =
    if feedbackProbes then
      ''
        runHook preBuild
        for probe in vi cps; do
          python3 ${../scripts/build-fullio-feedback-probe.py} "$probe" "$src" "$probe.conf"
          alsatplg -c "$probe.conf" -o "$probe.bin"
        done
        sha256sum -c <<'EOF'
        0b0d94e16b5389d2b4df194edb6983c1e033be554fbd13c2d28366eced1204f9  vi.bin
        75518e11e505b644a661fb92b633f553875b38e6d54843a3d296fe75e90ed416  cps.bin
        EOF
        runHook postBuild
      ''
    else
      ''
        runHook preBuild
        alsatplg -c "$src" -o fullio-v19c.bin
        echo 'e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0  fullio-v19c.bin' | sha256sum -c -
        python3 ${../tests/fullio-topology.py} fullio-v19c.bin --self-test
        runHook postBuild
      '';
  # Reference/test output only. Deliberately not a hardware.firmware layout.
  installPhase = ''
    runHook preInstall
    ${
      if feedbackProbes then
        ''
          install -Dm644 vi.bin "$out/share/sp11-fullio/probe-vi.bin"
          install -Dm644 cps.bin "$out/share/sp11-fullio/probe-cps.bin"
        ''
      else
        ''
          install -Dm644 fullio-v19c.bin "$out/share/sp11-fullio/v19c.bin"
        ''
    }
    runHook postInstall
  '';
}
