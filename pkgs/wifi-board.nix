{
  runCommandNoCC,
  fetchurl,
  python3,
  zstd,
  linux-firmware,
}:
let
  encoder = fetchurl {
    url = "https://raw.githubusercontent.com/qualcomm/qca-swiss-army-knife/6df4dae3e2f5e4c2903f3cafd40996fc1b3639ce/tools/scripts/ath12k/ath12k-bdencoder";
    sha256 = "fdcc8dc9628d67e500d496a1de22e82e136ddeaec32669ea1b3add93f2980652";
  };
  path = "lib/firmware/ath12k/WCN7850/hw2.0";
  # Same WCN7850 fallback board as dwhinham/archlinux-repo's sp11-ath12k-board.
  board = "bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=3378,qmi-chip-id=2,qmi-board-id=255";
in
runCommandNoCC "denali-wcn7850-board"
  {
    nativeBuildInputs = [
      python3
      zstd
    ];
  }
  ''
    fw=${linux-firmware}/${path}/board-2.bin
    if [ -f "$fw" ]; then
      cp "$fw" board-2.bin
    else
      zstd -d "$fw.zst" -o board-2.bin
    fi
    python ${encoder} --extract board-2.bin
    install -Dm644 '${board}.bin' "$out/${path}/board.bin"
  ''
