# CHECKLIST_MANUAL — Smoke tests com hardware físico

Sprints cujos DoDs exigem DualSense conectado. Revisor com hardware marca `[x]` antes de cada release. Substitui runtime no CI quando validação de hardware é necessária (meta-regra 9.8 do arquivo global do CLI de IA).

---

## W1.3 — Daemon loop básico

- [ ] `hefesto-dualsense4unix daemon start --foreground` conecta ao DualSense USB, mostra bateria e stick L.
- [ ] `hefesto-dualsense4unix daemon start --foreground` conecta ao DualSense BT, mostra bateria e stick L.
- [ ] `Ctrl+C` desliga limpo (sem resetar LED ou travar o controle).
- [ ] Desconectar cabo durante execução → daemon loga evento `disconnected` e volta a aceitar nova conexão.

## W3.0 — Resiliência sem hardware (BUG-DAEMON-NO-DEVICE-FATAL-01)

- [ ] Sem DualSense conectado, `systemctl --user start hefesto-dualsense4unix.service && sleep 5 && systemctl --user is-active …` → `active`.
- [ ] Socket `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock` existe sem hardware.
- [ ] `hefesto-dualsense4unix status` sem hardware → `connected: False`, sem traceback.
- [ ] Plug do DualSense (USB) com daemon offline → `connected: True` em ≤10s sem restart de unit.
- [ ] Unplug com daemon online → `connected: False`, daemon segue `active`.

## W3.0 — Tray runtime (CLUSTER-TRAY-POLISH-01 + IPC-STATE-PROFILE)

- [ ] `gnome-extensions list --enabled | grep ubuntu-appindicators` → presente após `install.sh --yes` + logout/login.
- [ ] Tray icon visível na barra superior do GNOME, clicável.
- [ ] Submenu "Perfis" lista apenas perfis reais (sem "(carregando)" zombie).
- [ ] Perfil `meu_perfil` aparece como `meu_perfil` (não `meu__perfil`).
- [ ] Click em perfil X com firefox aberto: perfil X persiste por 30s (autoswitch suprimido), depois autoswitch volta a operar.
- [ ] "Sair" do tray com daemon iniciado fora do systemd: `pgrep -af hefesto | grep -v grep` retorna vazio.

## W3.0 — Firmware tab (FEAT-FIRMWARE-DUALSENSECTL-INSTALL-01)

- [ ] Sem `dualsensectl` instalado: aba Firmware mostra mensagem "dualsensectl não instalado — instalar via Flathub" (não silencia).
- [ ] Após `flatpak install -y --user flathub com.github.nowrep.dualsensectl`: `dualsensectl info` retorna firmware version do controle.

## W3.0 — Bluetooth (FEAT-BLUETOOTH-CONNECTION-01)

- [ ] Pareamento via `bluetoothctl pair/trust/connect <MAC>` funciona.
- [ ] DualSense conectado **só** via BT (USB desplugado): `hefesto-dualsense4unix status` → `transport: bt`.
- [ ] Lightbar via BT: `hefesto-dualsense4unix led --color "#FF00FF"` acende magenta.
- [ ] Trigger via BT: `profile activate shooter` aplica Rigid em L2/R2.
- [ ] Hotplug GUI BT (se `--enable-hotplug-gui`): desconectar BT + reconectar abre a GUI.

## W2.2 — Trigger effects e rumble

- [ ] Cada um dos 19 modos produz vibração correta em `L2` e `R2` via `hefesto-dualsense4unix test trigger --mode <X> --side <lado>`.
- [ ] `hefesto-dualsense4unix led --color FF0080` acende lightbar na cor esperada.
- [ ] Rumble weak/strong independentes; throttle anti-spam não bloqueia comandos legítimos.

## W3.2 — Perfis

- [ ] `hefesto-dualsense4unix profile activate <nome>` muda efeito no controle em menos de 100ms.
- [ ] `hefesto-dualsense4unix profile show <nome>` reflete o que está aplicado.

## W4.3 — UDP compat DSX

- [ ] `python examples/mod_integration_udp.py` muda trigger em tempo real.
- [ ] Rate limit dropa com log `warn` quando cliente ultrapassa 1000 pkt/s.
- [ ] `version != 1` no payload gera log `warn` e drop silencioso.

## W5.x — TUI

Cada PR que toca `src/hefesto_dualsense4unix/tui/**` inclui no body:

- [ ] `scrot /tmp/hefesto_tui_<area>_<ts>.png` anexado.
- [ ] `sha256sum` do PNG registrado.
- [ ] Descrição multimodal de 3–5 linhas cobrindo: elementos visíveis, acentuação PT-BR correta, contraste, layout.

Áreas a cobrir:
- [ ] Screen principal (status do daemon, perfil ativo).
- [ ] Screen de perfis (lista, ativação).
- [ ] Screen de teste de trigger (preview animado).
- [ ] Screen de settings.
- [ ] Status bar com bateria + conexão.

## W6.1 — Window detection X11

- [ ] `hefesto-dualsense4unix daemon logs` mostra mudança de `wm_class` ao trocar de janela ativa.
- [ ] Lançar Cyberpunk via Steam → log reporta `exe_basename=Cyberpunk2077.exe`.
- [ ] Alt-tab rápido entre 3 janelas não dispara auto-switch (debounce 500ms).

## W6.3 — Gamepad virtual

- [ ] `hefesto-dualsense4unix emulate xbox360 --on` cria `/dev/input/js*` visível para jogos.
- [ ] Jogo que só reconhece Xbox360 recebe input correto.
- [ ] Combo PS + D-pad troca perfil sem vazar para o uinput (buffer 150ms).
- [ ] `hefesto-dualsense4unix emulate xbox360 --off` remove o device virtual sem crash.

## W8.1 — Hotkeys

- [ ] Combo configurado em `daemon.toml` troca perfil com janela de jogo em foco.
- [ ] Modo `--unsafe-keyboard-hotkeys` exibe aviso de risco antes de ativar.

## Onda multicontrole+dedup — cores automáticas, cards e perfis por controle (2026-07-17)

Pré-requisito: `./uninstall.sh && ./install.sh` SEM flags (instala o wrapper
`hefesto-launch`, o quirk do mic e migra o vdf com a Steam fechada) + daemon novo.

### COR-07 — cores e LED automáticos (2 DualSense: 1 BT + 1 cabo)

- [ ] Ligar o daemon com os 2 DualSense → cada um acende cor DIFERENTE + LED do
      seu número sozinho, nos dois transportes (tolerar o pisca breve do kernel
      no bind — o estado FINAL é o que vale).
- [ ] Replugar o Controle 1 → volta com a MESMA cor/número.
- [ ] Escolher cor manual para o controle BT (alvo "Controle N" na aba
      Lightbar) → sobrevive a replug e a restart do daemon.
- [ ] Salvar o perfil "vitoria", fechar e reabrir a GUI → tudo como deixou.
- [ ] Jogo em Modo Nativo → o hefesto NÃO pisa nos LEDs do jogo.
- [ ] Co-op num jogo real: conferir LED aceso vs número de player que o JOGO
      mostra — se divergirem (borda de replug do primário), é o comportamento
      documentado ("número do controle" ≠ "número do jogador"): anotar o passo,
      não é reprovação.

### STATUS-05 — aba Status em cards (2 DualSense)

- [ ] 2 cards, cada um com a cor do PRÓPRIO lightbar (swatch cru + traços
      clareados legíveis), número e bateria próprios.
- [ ] Mexer cada controle → só o card dele acende.
- [ ] Aceite explícito do compromisso da cor: swatch = cor crua; traços = mesma
      matiz, clareada para dar contraste (não é literalmente "a mesma cor"
      quando o lightbar está escuro). Rejeitar aqui = decisão de design, não bug.
- [ ] Screenshot da aba anexado ao doc do sprint.

### PERFIL-05 — perfis por controle (o que falta da validação humana)

- [ ] (a) Cores/gatilhos DIFERENTES por controle no perfil `vitoria`; desplugar
      e replugar o do cabo → cada um mantém a SUA cor (sem contaminação).
- [ ] (c) Desligar/religar o controle BT (botão PS religa) → o override
      por-controle re-aplica sozinho quando ele volta.
- [ ] (d) Trocar o MESMO controle de cabo para BT → mesma identidade, mesmos
      settings (o MAC é a chave, provado estável nos dois transportes).

### Diálogo do wrapper (1x por jogo)

- [ ] Abrir um jogo Steam SEM a linha do `hefesto-launch` nas opções → o aviso
      aparece UMA vez, com a linha copiável; "Não perguntar para este jogo"
      cala aquele appid para sempre; o jogo segue jogável (pior caso: controle
      duplicado, nunca zero).

### 8BIT-05 — decisão de modo do 8BitDo (custo zero de código)

- [ ] Escolher o modo (cabo Switch = provadamente estável; X-input por cabo =
      Xbox 360 real sem gyro; X-input por BT = experimento) e jogar 10 min
      observando "descontrolado/inputs cancelados". Guia:
      `docs/usage/troubleshooting-8bitdo.md`.

---

## Matriz de distros testadas

| Distro          | Versão | USB | BT  | Tray | Observações |
|-----------------|--------|-----|-----|------|-------------|
| Pop!\_OS        | 22.04  | [ ] | [ ] | [ ]  |             |
| Ubuntu          | 22.04  | [ ] | [ ] | [ ]  |             |
| Fedora          | 39     | [ ] | [ ] | [ ]  |             |
| Arch            | rolling| [ ] | [ ] | [ ]  |             |
