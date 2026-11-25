{
  stdenv,
  fetchurl,
  makeWrapper,
  alsa-lib,
  alsa-utils,
  pipewire,
  python3,
  wireplumber,
}:
let
  rev = "3232e1dacdeb580a10a9cb8d4756a4518a7bd83e";
  pinned = path: sha256: fetchurl {
    url = "https://raw.githubusercontent.com/geocausa/SP11X1e-audio/${rev}/${path}";
    inherit sha256;
  };
  helper = name: hash: pinned "deploy/ubig/${name}" hash;
  sync = helper "sp11_windows_volume_transaction_sync.py"
    "f294740cb2c3a64d66df1f77b656cd9acfd444e08a909211b10a9e7f4c49c102";
  base = helper "sp11_ubig_volume_sync.py"
    "6979ec08b61218ce1bfdcdeee361fb2ea82c8e44425c3187f3978b5ad9adf559";
  msiir = helper "sp11_msiir_volume_sync.py"
    "721c80a05b92baa87163d941ab8045cc89f7d067dc641d6eb01e31f6898c6f03";
  deltas = helper "sp11_gainstep_runtime_deltas.json"
    "2077bea085cea94f52853b8524205824ea36ac038522d7b2f93906c84756337e";
  tlvWriter = pinned "tools/tlv_write.c"
    "b949dcaec71712f0149e156b7e9436b27756280bc90e36c9355a9bbf4c1809d7";
in
stdenv.mkDerivation {
  pname = "sp11-fullio-v19c-volume-transaction";
  version = "3232e1d";
  dontUnpack = true;
  dontConfigure = true;
  nativeBuildInputs = [ makeWrapper ];
  buildInputs = [ alsa-lib ];

  buildPhase = ''
    runHook preBuild
    "$CC" -std=gnu11 -O2 ${tlvWriter} -lasound -o tlv_write
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    helpers="$out/libexec/sp11-fullio"
    install -Dm755 tlv_write "$helpers/tlv_write"
    install -Dm644 ${sync} "$helpers/volume-transaction.py"
    install -m644 ${base} "$helpers/sp11-ubig-volume-sync"
    install -m644 ${msiir} "$helpers/sp11-msiir-volume-sync"
    install -Dm644 ${deltas} "$out/share/sp11-fullio/gainstep-runtime-deltas.json"
    mkdir -p "$out/bin"
    makeWrapper ${python3}/bin/python3 "$out/bin/sp11-windows-volume-transaction-sync" \
      --set UBIG_VOLUME_HELPER_DIR "$helpers" \
      --add-flags "$helpers/volume-transaction.py" \
      --add-flags "--tlv-write $helpers/tlv_write" \
      --add-flags "--delta-table $out/share/sp11-fullio/gainstep-runtime-deltas.json" \
      --add-flags "--amixer ${alsa-utils}/bin/amixer --pw-dump ${pipewire}/bin/pw-dump --wpctl ${wireplumber}/bin/wpctl"
    runHook postInstall
  '';
}
