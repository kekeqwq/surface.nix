final: _prev: {
  surfacePackages = final.lib.makeScope final.newScope (self: {
    linux = self.callPackage ./pkgs/linux-sp11-7.3.nix { kernelPatches = [ ]; };
    linuxPackages = final.linuxPackagesFor self.linux;
    wifiBoard = self.callPackage ./pkgs/wifi-board.nix { };
  });
}
