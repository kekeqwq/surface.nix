final: _prev: {
  surfacePackages = final.lib.makeScope final.newScope (self: {
    linux = self.callPackage ./pkgs/linux-sp11-7.3.nix { kernelPatches = [ ]; };
    linuxPackages = final.linuxPackagesFor self.linux;
    surfaceNext = self.callPackage ./pkgs/surface-next.nix { kernelPatches = [ ]; };
    surfaceNextPackages = final.linuxPackagesFor self.surfaceNext;
    surfaceNextTouch = self.surfaceNext.override {
      kernelPatches = self.callPackage ./pkgs/touch-patches.nix { };
      localVersion = "-surface-touch";
      configfile = builtins.toFile "surface-next-touch.config" (
        builtins.readFile ./pkgs/config-sp11-7.3.aarch64
        + "\nCONFIG_SPI_HID=m\nCONFIG_SPI_HID_OF=m\n"
      );
    };
    surfaceNextTouchPackages = final.linuxPackagesFor self.surfaceNextTouch;
    wifiBoard = self.callPackage ./pkgs/wifi-board.nix { };
    audioTopology = self.callPackage ./pkgs/audio-topology.nix { };
    alsaUcm = _prev.alsa-ucm-conf.overrideAttrs (old: {
      patches = (old.patches or [ ]) ++ [ (final.fetchurl {
        # Surface Pro 11 routing; upstream PR #847, not a kernel patch.
        url = "https://github.com/alsa-project/alsa-ucm-conf/commit/badb04bdff4ee808f2609d4eb270101a6212f0f2.patch";
        hash = "sha256-PHroTQAJRPQDRCC7YrFXIjhX4JuHSXevvhrxNQ9raQQ=";
      }) ];
    });
  });
}
