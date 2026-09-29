# O Hefesto no COSMIC

O COSMIC (Pop!_OS 24.04) é onde o Hefesto é testado com controles.

| Recurso | Estado |
|---|---|
| controles pelo cabo e pelo Bluetooth, atalhos, mouse e teclado do controle | funcionam, sem depender da sessão gráfica |
| a janela | abre pelo XWayland |
| o ícone da bandeja | aparece na área de status do painel |
| a troca automática de perfil | funciona para jogos em XWayland (o que inclui a Steam e o Proton) |

## O ícone da bandeja

O ícone aparece na área de status do painel do COSMIC, sem configuração. Se não
aparecer, confira em Configurações, Painel, se o miniaplicativo da área de
status está no painel. O menu dele abre a janela, troca de perfil e mostra o
estado.

O antigo miniaplicativo próprio do COSMIC foi aposentado: o ícone da bandeja faz
o mesmo e funciona fora do COSMIC. Quem ainda o quiser pode compilá-lo com
`./install.sh --enable-cosmic-applet`.

## A troca automática de perfil

O Hefesto descobre o jogo em foco pela janela. No COSMIC:

- **janelas XWayland** (a Steam, os jogos pelo Proton e a maioria dos jogos):
  funciona. Com `DISPLAY` e `WAYLAND_DISPLAY` definidos, o Hefesto usa o X11;
- **janelas Wayland nativas**: o COSMIC não oferece ao Hefesto como saber qual
  janela está em foco (nem o `wlr-foreign-toplevel-management`, que o `wlrctl`
  usa, nem o portal `GetActiveWindow`). Sem essa informação, o perfil ativo
  continua valendo; troque pela janela, pela linha de comando ou com PS +
  direcional.

No diário do serviço, `window_backend_selected backend=xlib` confirma o X11, e
`autoswitch_compositor_unsupported` diz que o compositor não informou a janela.
A decisão técnica está em [ADR-014](../adr/014-cosmic-wayland-support.md).

## Instalar

O `./install.sh` padrão serve para o COSMIC. Duas opções que podem interessar:

- `--enable-hotplug-gui` abre a janela do Hefesto no início da sessão (ver
  [hotplug.md](hotplug.md));
- `--keep-steam-input` mantém o Steam Input ligado (ver
  [jogos-e-mascaras.md](jogos-e-mascaras.md)).
