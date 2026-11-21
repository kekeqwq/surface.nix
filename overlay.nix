final: prev: {
  surfacePackages = final.lib.makeScope final.newScope (self: {
    surfaceNext = self.callPackage ./pkgs/surface-next.nix {
      kernelPatches = self.callPackage ./pkgs/touch-patches.nix { };
    };
    kernelPackages = final.linuxPackagesFor self.surfaceNext;
    wifiBoard = self.callPackage ./pkgs/wifi-board.nix { };
    audioTopology = self.callPackage ./pkgs/audio-topology.nix { };
    alsaUcm = prev.alsa-ucm-conf.overrideAttrs (old: {
      patches = (old.patches or [ ]) ++ [
        (final.fetchurl {
          url = "https://github.com/alsa-project/alsa-ucm-conf/commit/badb04bdff4ee808f2609d4eb270101a6212f0f2.patch";
          hash = "sha256-PHroTQAJRPQDRCC7YrFXIjhX4JuHSXevvhrxNQ9raQQ=";
        })
      ];
    });
  });
}
