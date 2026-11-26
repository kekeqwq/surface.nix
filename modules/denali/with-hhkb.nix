# Keep the existing kernel derivation exactly when the keyboard experiment is off.
{ enabled, kernel }:
if !enabled then
  kernel
else
  kernel.override {
    kernelPatches = kernel.kernelPatches ++ [
      {
        name = "denali-hhkb";
        patch = ../../pkgs/patches/denali-hhkb.patch;
      }
    ];
  }
