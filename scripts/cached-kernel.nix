# Opt-in local diagnostic builds only. The caller must create cacheDirectory
# (root:nixbld, mode 0770) and pass --option extra-sandbox-paths cacheDirectory.
# This is not enabled in the public hardware module or normal system builds.
{
  pkgs,
  kernel,
  cacheDirectory ? "/var/cache/surface-kernel-ccache",
}:
kernel.override {
  linuxManualConfig = pkgs.linuxManualConfig.override {
    stdenv = pkgs.ccacheStdenv.override {
      extraConfig = ''
        export CCACHE_DIR=${pkgs.lib.escapeShellArg cacheDirectory}
        export CCACHE_UMASK=007
        export CCACHE_COMPRESS=1
        export CCACHE_MAXSIZE=16G
        # Nix compiler wrappers add a per-derivation random seed.
        export CCACHE_SLOPPINESS=random_seed
      '';
    };
  };
}
