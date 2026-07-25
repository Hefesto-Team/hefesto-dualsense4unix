# Abrir a janela sozinha — o que existe e o que foi retirado

> **Leia isto primeiro: o hotplug por udev não existe mais.** Até junho de 2026
> o Hefesto instalava duas regras de udev (`73-ps5-controller-hotplug.rules` e
> `74-ps5-controller-hotplug-bt.rules`) que disparavam a janela no momento em
> que o controle era plugado ou pareado. Elas foram **descontinuadas em
> 23/06/2026 e removidas do repositório em 18/07/2026**: abriam o controle via
> `hidraw` a cada `ACTION=="add"`, o que amplificava a re-enumeração do storm
> `-71`. O `scripts/install_udev.sh` ainda apaga as duas de instalações antigas.
>
> Se você chegou aqui procurando "a janela abre ao plugar": **não abre**. O que
> sobrou está descrito abaixo, e o nome da unit (`...-gui-hotplug.service`) é
> herança do mecanismo antigo.

## O que existe hoje

Uma unit `systemd --user` opcional:

`~/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service`

```ini
[Unit]
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.local/bin/hefesto-dualsense4unix-gui

[Install]
WantedBy=graphical-session.target
```

O gatilho é `graphical-session.target` — ou seja, ela abre a janela **no início
da sessão gráfica**, uma vez, não quando o controle chega. Não há mais nenhuma
regra de udev que a acione (a única regra do projeto que fala com o systemd hoje
é a `83`, e ela dispara o snapshot de pareamentos Bluetooth, não a janela).

A unit não tem guarda `pgrep`: quem cuida de não abrir duas janelas é o próprio
launcher, via `acquire_or_bring_to_front` — se já existe uma janela, ele a traz
para a frente e sai com código 0.

## Habilitar

É **opt-in, e o padrão é não instalar**. No passo 7/11 o `install.sh` pergunta
"abrir GUI automaticamente ao plugar DualSense?" com padrão **não**:

```bash
./install.sh --enable-hotplug-gui   # instala e habilita sem perguntar
./install.sh --no-hotplug-gui       # pula o passo inteiro
```

Sob `--yes` a resposta padrão (não) é a que vale — `--yes` não liga a unit.

Manualmente, depois:

```bash
mkdir -p ~/.config/systemd/user
cp assets/hefesto-dualsense4unix-gui-hotplug.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable hefesto-dualsense4unix-gui-hotplug.service
```

## Desabilitar

```bash
systemctl --user disable hefesto-dualsense4unix-gui-hotplug.service
rm ~/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service
systemctl --user daemon-reload
```

O `./uninstall.sh` já faz isso.

## Verificar

```bash
systemctl --user is-enabled hefesto-dualsense4unix-gui-hotplug.service
systemctl --user start hefesto-dualsense4unix-gui-hotplug.service   # deve abrir a janela
```

## Limitações

- **Sessões sem `systemd-logind`** (Alpine/Void/Artix OpenRC): `graphical-session.target`
  não existe; a unit não tem como ser acionada. Ver
  [ADR-009](../adr/009-systemd-logind-scope.md).
- **Sessões antigas** podem não propagar `DISPLAY`/`WAYLAND_DISPLAY` para o
  systemd `--user`; nelas a unit sobe e a janela não aparece.
- Reconectar o controle no meio da sessão **não** reabre a janela. Abra pelo
  menu de aplicativos, pelo applet COSMIC ou por `hefesto-dualsense4unix-gui`.

## E se eu quiser mesmo o gatilho por plugar?

Não há caminho suportado hoje, e reintroduzir a regra antiga traz de volta a
causa do storm `-71`. Um caminho que **não** abre o `hidraw` seria uma regra que
apenas marca o device com `TAG+="systemd"` e um
`SYSTEMD_USER_WANTS` apontando para esta unit — mas isso não está implementado
nem medido aqui, e fica registrado como ideia, não como receita.
