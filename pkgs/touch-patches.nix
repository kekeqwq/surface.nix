# Dependency-ordered SPI-HID v7 + GENI/GPI QSPI + Denali digitizer queue.
# Reference: dwhinham/linux-sp11@46bb6beace94874a3ec602bfb83e6f87995bc5d0.
# Keep upstream authorship in each pinned commit patch. No unrelated audio,
# power, modem or graphics patches are included.
{ fetchurl }:
map (spec: {
  name = "surface-touch-${builtins.substring 0 12 spec.rev}";
  patch = if spec.rev == "f285d9b23cd3e8d947c6914bc3bcae227256e7e1"
    then ./patches/geni-qspi-next-20261118.patch
    else fetchurl {
      name = "${spec.rev}.patch";
      url = "https://github.com/dwhinham/linux-sp11/commit/${spec.rev}.patch";
      inherit (spec) hash;
    };
}) [
  { rev = "e763b6a9ae736109b948d37127778a8831a02d76"; hash = "sha256-PlE9hdzOwbk+XuEI6RqYL9pFi6RmUgyNdOTlI6/BIlg="; }
  { rev = "3e4d4ed036ea3f93c8d7354a9940af601b3769ae"; hash = "sha256-xITJAQjUHmiLZc4IqQQ3+jA1zm5NGbq2MOEGH1xnPxE="; }
  { rev = "aae1463eb405eb327f06934bded31b230c8f3cc0"; hash = "sha256-0P8RwH+jD0XcVGZQZkN/sDHd8j8J6SGigFd+t6lZ+4Y="; }
  { rev = "bb9cdd3975b22d5735127571d6f43bb745c28dff"; hash = "sha256-HSd3cpC9FNM6CBZtSAogJBya9/yMwSLn4hMF6Pvv5ao="; }
  { rev = "8347f85bf0a2ed60205819a5cd90687763df3854"; hash = "sha256-IOGHmWzbAkhUtTXGBqVtI6aAvCSklT5JdYpyc2f6E3c="; }
  { rev = "987067e1d1e772f718847772243cff4dbad2ddd5"; hash = "sha256-4fyxFc7aS7xF3jZDWtDYfK0wEXt5ZlTWnOTyRLMPb9c="; }
  { rev = "7ddb64dcaecf0ce999eac1748e04e85fc71f39cf"; hash = "sha256-B5fxZZLE5vb/gTAPhX4kz9sIHaIOClWO74rgvb2rA2A="; }
  { rev = "bc2bfcc8663bf5971486b820db1165dd407b0d6c"; hash = "sha256-z1gL/22dVBn+IfPX1z7TBbdjABadQrbttuo1GysdpbA="; }
  { rev = "480a468f8086b87b3c23721416c5889c7c77b01f"; hash = "sha256-0SBQ/95j6/QYJQabB2jMSgwiMc9g7HMX0c0MY9pkDE4="; }
  { rev = "f285d9b23cd3e8d947c6914bc3bcae227256e7e1"; hash = "sha256-Pd/1i+9Jag0+vMsK5t07HCvXpscxwKT6R1Cd98MyzO8="; }
  { rev = "1edf5d0930d545fdf6c40dfc927aa61232772804"; hash = "sha256-qO1PNkj375muVpB0onsPGVpsuzss/ay+epXDvfa/Bn0="; }
  { rev = "d6a5ceebc9b674a8f7b865c40845ff994dbf9bb4"; hash = "sha256-yWUtNmN4UlWfCu/MsIznqPaQaRzHMM89JY9nscWq9Es="; }
  { rev = "bef8979c642e458b91d67038b62e3f9840ed1f59"; hash = "sha256-Xh3R5vkVvio2H+k8i7YVehm/HSPCcjxoFD6hgXP/Uls="; }
  { rev = "c4114bda1e3e3b9bfee62934cdd1464078c27081"; hash = "sha256-4kgOFCABnWb37mbVJxljfuS5uSB6zBtubGwrise6FkM="; }
  { rev = "5d136dbde5847f8df3d37da49d5de973380176c1"; hash = "sha256-jzR5bRiIfJpQn73WN/5X3aX5f2ZVhpZ8dDVObP1Gn0w="; }
  { rev = "e2590e1328af4d83c1e8d2c18250840772391dce"; hash = "sha256-0nxUxhd/h1wDCrvoDrpOXdwaRloqnR1HGiniYtSa8B4="; }
  { rev = "c5afea99480020f27e04606218c1da8ab3e2f96f"; hash = "sha256-8PNfLNYt3WFwNGMSNZV9OUxigjGSn0U01RXQRKs4PwQ="; }
  { rev = "168658bd590d804f1ae35a1c3dab3a059700e04f"; hash = "sha256-Tlf5v/PJX1w41j0C+GyTxt6XZo4rUj/UhFK6tLjcQqA="; }
]
