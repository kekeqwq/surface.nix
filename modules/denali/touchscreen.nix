{
  config,
  lib,
  pkgs,
  ...
}:
let
  node = "/dev/surface/denali/ipts";
  deviceUnit = "dev-surface-denali-ipts.device";
  service = "denali-iptsd";
  rules = pkgs.runCommand "denali-iptsd-rules" { } ''
    install -d "$out/lib/udev/rules.d"
    stock=${pkgs.iptsd}/lib/udev/rules.d/50-iptsd.rules
    if [ ! -f "$stock" ]; then
      stock=${pkgs.iptsd}/etc/udev/rules.d/50-iptsd.rules
    fi
    test -f "$stock"
    {
      cat <<'RULES'
    SUBSYSTEM=="hidraw", KERNELS=="0019:045E:09AF.*", GOTO="denali_iptsd_end"
    SUBSYSTEM=="hidraw", KERNELS=="001C:045E:0C83.*", GOTO="denali_iptsd_touchscreen"
    RULES
      cat "$stock"
      printf '\n'
      cat <<'RULES'
    GOTO="denali_iptsd_end"
    LABEL="denali_iptsd_touchscreen"
    ACTION=="add|change", SYMLINK+="surface/denali/ipts", TAG+="systemd", \
      ENV{SYSTEMD_ALIAS}+="${node}", ENV{SYSTEMD_WANTS}+="${service}.service"
    LABEL="denali_iptsd_end"
    RULES
    } > "$out/lib/udev/rules.d/50-iptsd.rules"
  '';
in
{
  config = lib.mkIf config.surface.devices.denali.enable {
    services.iptsd.enable = lib.mkDefault true;

    # Replace the packaged rule in-place: do not let its numbered PROGRAM
    # probe run on either device sharing that number at boot. Other devices
    # still run the unmodified packaged rules below the two early branches.
    services.udev.packages = lib.mkIf config.services.iptsd.enable (lib.mkAfter [ rules ]);

    systemd.services.${service} = lib.mkIf config.services.iptsd.enable {
      description = "Denali touchscreen and stylus (IPTSD)";
      # The raw numeric node can be briefly assigned to the magnetic touchpad
      # during boot. Order against and follow only the verified touchscreen.
      bindsTo = [ deviceUnit ];
      after = [ deviceUnit ];
      restartTriggers = [ config.environment.etc."iptsd.conf".source ];
      serviceConfig.ExecStart = "${lib.getExe' pkgs.iptsd "iptsd"} ${node}";
    };
  };
}
