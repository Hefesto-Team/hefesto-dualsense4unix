# ADR-013: USB autosuspend desabilitado per-device para DualSense

**Status:** aceito

## Contexto

O kernel Linux com `CONFIG_USB_RUNTIME_PM=y` (default em Pop!_OS, Ubuntu, Fedora) suspende automaticamente dispositivos USB inativos após ~2 s. Para um gamepad em polling HID a 60–120 Hz o comportamento é patológico: o kernel suspende o device, o próximo `read()` do hidraw devolve `ENODEV`, o daemon entra em reconnect loop, a GUI exibe "daemon offline" ou "tentando reconectar" com o controle fisicamente ligado. Logs de `systemd-udev` mostram `power/runtime_status` alternando entre `active` e `suspended`.

Causa-raiz foi descoberta em projeto irmão (desbloqueador Nintendo Switch) onde o mesmo sintoma aparecia durante transferências USB de payload RCM. A solução lá foi em três camadas: udev rule + fallback programático em `/sys/bus/usb/devices/*/power/` + error handling distinguindo `ENODEV` de `EPERM`/`EACCES`. A udev rule canônica do projeto irmão já aplica no `SUBSYSTEM=="usb"` — forma semanticamente correta (o atributo `power/` fica no nó-pai USB, não em children como `hidraw`). Esse ADR preserva a mesma forma.

Para o Hefesto a camada udev basta — não há injeção privilegiada, apenas polling contínuo.

## Decisão

Arquivo `assets/72-ps5-controller-autosuspend.rules` aplica no `subsystem=usb` (não `hidraw` — o atributo `power/` fica no nó-pai USB):

```
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="054c", ATTR{idProduct}=="0ce6", \
    ATTR{power/control}="on", ATTR{power/autosuspend_delay_ms}="-1"
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="054c", ATTR{idProduct}=="0df2", \
    ATTR{power/control}="on", ATTR{power/autosuspend_delay_ms}="-1"
```

Cobre DualSense standard (`054c:0ce6`) e DualSense Edge (`054c:0df2`). Instalação via `scripts/install_udev.sh` (ou do `install.sh` principal orquestrado). `udevadm trigger --action=change --subsystem-match=usb` adicional para aplicar a controles já plugados sem exigir unplug.

## Consequências

(+) Eliminação de desconexão transiente em polling contínuo — causa-raiz resolvida, não sintoma mascarado.
(+) Regra cirúrgica (per-VID/PID), não global (`/sys/module/usbcore/parameters/autosuspend`). Zero impacto em outros devices USB.
(+) Funciona desde hotplug (`ACTION=="add"`) — novo controle já conecta com `power/control=on`.
(−) Requer sudo para instalar a udev rule (mesma barreira já existente para `70-ps5-controller.rules`).
(−) Bluetooth não é coberto — BT sofre timeout L2CAP separado, issue distinta fora deste ADR.
(−) Ao reaplicar apenas via `udevadm trigger` sem `--action=change`, a regra `ACTION=="add"` não roda. Instalador precisa chamar `--action=change --subsystem-match=usb` para aplicar imediatamente.
