# Surface TODO

[免重启验证记录与后续实机门槛](docs/denali-power-touch-no-reboot.md)（2026-11-28）。

## TODO-#1：评估免 `iptsd` 的 Denali 触屏驱动

- [ ] 用当前锁定的 `surface-next` 试编译 [`geocausa/SP11X1e-touchscreen` 的 `production-v1`](https://github.com/geocausa/SP11X1e-touchscreen/tree/1cb0ce2b3cc95821433410081b6cbba634eddc41/production-v1) 树外模块。先核对 GENI/GPI 传输和设备树的 IRQ、供电、复位，不为此更换日用内核基线。
- [ ] 若兼容，在 `surface.nix` 做成随内核构建、锁定源码的可选模块。新驱动和 `SPI-HID + iptsd` 互斥；不开实验就保留现有基线。主机选择留在 `flakes`。
- [ ] 在这台 Denali OLED 验证多次冷启动和挂起唤醒、点按/拖动/捏合、HHKB 与触控板不受影响，并确认实验路径不运行触屏 daemon。单独记录回退验证；候选只有手指触控，不把笔输入列为已支持。

## TODO-#2：同步修复 Denali 电池读数与挂起/唤醒

保留现有合盖只锁屏的策略：这是挂起尚未验收时的主动选择。用当前锁定的 `surface-next` 逐项验证；本项处理 `s2idle` / `deep`，不引入磁盘休眠。与 TODO-#1 分开验证，避免同时更换触屏栈。

- [ ] **电池读数与充电分开验收。** 同一电池曾同时报 `BAT1=80%`、`qcom-battmgr-bat=100%`。让 Surface 的 Waybar 和锁屏统一选 `BAT1`，不改共享默认行为、不先禁用 Qualcomm 驱动或写入充电阈值。拔插验证电源状态、充放电方向和 `energy_now`，再判断是否需做驱动级仲裁。参考 [dwhinham 的 SAM 电池选源](https://github.com/dwhinham/linux-surface-pro-11#post-install-fixups)。
- [ ] **先建立本机基线。** 在有人值守、保留可启动回退代的前提下，分别做 `deep` 和 `s2idle` 的短时手动挂起，记录实际模式、唤醒源、内核与设备恢复时间。短测通过后，对已通过的模式做 ≥2 小时中等电量、电池供电的对照；拔掉电源、外屏和 USB 外设，保持网络条件一致，记录 `BAT1/energy_now`、稳定后的读数及 Qualcomm `CXSD`/`AOSD`/`DDR` 驻留率。清醒空闲功耗另测。
- [ ] **逐项对照，不移植整套内核。** 参考 [geocausa 的 suspend archive @ `0376e25`](https://github.com/geocausa/sp11-suspend-resume-public/tree/0376e25)、[Omarchy 同款 OLED 低功耗补丁](https://github.com/omacom/omarchy-pkgs/blob/master/pkgbuilds/linux-omarchy-aarch64/README.md#surface-pro-11)、[turbineBMW 旧 PSCI guard 与 logind watchdog](https://github.com/turbineBMW/surface-pro-11-linux/blob/main/docs/SUSPEND.md) 和 [OE 的 deep 记录](https://github.com/ooaklee/linux-surface-pro-11-oe/issues/39)。先查 GMU 绑定与 QCE/互连 `sync_state()`，比较禁用无用 DT 节点与仅 PM 绑定 QCE（不启用加密算法）；若仍见频繁 ADSP 唤醒，再对照 PLD GLINK，不能只靠 SMP2P bit 12。只在复现对应症状时考虑 GENI UART、PSCI、Wi-Fi 或显示补丁。
- [ ] **FullIO 是硬性验收门槛。** 若低功耗数据指向 WSA 空闲时钟票，单独评估释放与恢复；不强关共享电源轨，不合入重置/重绑规避。每轮检查 OLED、NVMe、Wi-Fi、BT、HHKB/触控板/触屏，以及首轮受保护扬声器与 MicArray 同时工作，维持 0 dB 和现有 fail-closed 保护。连续挂起、长时耗电、外设唤醒边界和回退均通过后，才考虑在 `flakes` 改合盖策略。

参考数据不是本机验收：geocausa 的独立试验约 0.163 W（80.8 分钟），并记录了间歇性 SoundWire 唤醒异常；Omarchy 同款 OLED 约 0.23–0.25 W。

## TODO-#3：桌面全局亮暗热切换（Catppuccin Latte / Mocha）— 已收尾

用户确认结束本项。基础亮暗切换和实机 Auto 时间边界已验收；后续 Waybar 圆角、面板配色、日历与托盘重绘补丁已正式部署。托盘补丁的双向换色已在隔离环境验证，补丁版实机 Auto 跨边界未补验。Prism Launcher 暂不处理，不承诺通用 Qt 应用热重载。下面保留原验收范围，未勾选不代表继续开展本项。

- [x] 在 `flakes` 的共享 Linux 桌面实现一个用户级外观状态；控制中心展示 **自动 / 亮色 / 暗色** 三个选项，对应定时和手动两种模式。手动点亮/暗立即切到手动并持久化；切回自动，立即按本地时间计算：`07:00 ≤ 时间 < 18:00` 用 Latte，其余用 Mocha。登录、唤醒、时区和系统时钟变化后重新计算；不改系统时间，不要求重启或注销，不引入常驻轮询。
- [ ] 统一两套配色和刷新入口，验收 Niri（边框、焦点、概览等）、Mako 通知、Waybar、Rofi、已打开的控制中心及输入法界面。不重启合成器、不终止窗口或应用。GTK/Qt 及 portal 发布一致的外观偏好；记录不支持运行中重绘、只能下次打开时继承的第三方应用，不承诺任意应用强制热切换。
- [ ] 验证已打开的 Ghostty 窗口通过现有 Latte/Mocha 双主题跟随外观；让运行中的 Emacs（含 daemon 的已有 frame、新 frame）在不丢缓冲区、不重启的条件下切换。锁屏在启动时取当前外观；若要跨定时边界刷新已锁定画面，必须在原锁会话内完成，绝不解锁或重启锁屏。Plymouth 开关机动画保持原样，不读取外观状态或时钟。
- [ ] 测 `06:59 / 07:00 / 17:59 / 18:00`、自动中点击亮/暗、手动跨越时间边界、切回自动立即生效、重新登录/唤醒补算以及快速连续切换。实机检查前景对比度、状态色和已打开应用；切换失败时保留可用主题，不能影响锁屏、壁纸、Niri 布局或声音。
