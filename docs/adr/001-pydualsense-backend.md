# ADR-001: `pydualsense` como backend HID

**Status:** aceito — **EMENDADO em 2026-08-13** por
[ADR-020: o backend deixou de ser um só](020-o-backend-deixou-de-ser-um-so.md)

> **Leia o ADR-020 antes de agir sobre esta página.** A decisão abaixo continua
> valendo, e é ela que permitiu tudo o que veio depois: isolar o backend atrás
> de `IController` foi o que deixou o produto crescer sem reescrever o daemon.
> O que caducou é o **retrato**. Hoje a `pydualsense` é **uma** das camadas que
> falam com o aparelho, e cuida só do caminho de OUTPUT por hidraw — o INPUT vem
> do `evdev`, a cor por-controle vem do `sysfs`, o controle virtual é um device
> `uhid`, o hidraw do controle físico é guardado por um broker root, e há
> defeito de probe que só se cura por DKMS. O ADR-020 tem a tabela das seis
> camadas, com o arquivo de cada uma.
>
> Duas armadilhas que esta página, sozinha, deixa passar: o report `0x31` de
> Bluetooth montado pela `pydualsense` é malformado e o firmware o descarta (é
> por isso que o nosso sai de `core/ds_output_report.py`, validado contra o
> kernel), e escrever a lightbar por hidraw disputa com o `hid_playstation`,
> que é o dono desses nós de LED.

## Contexto
Três caminhos possíveis: implementar protocolo HID do zero, portar `trigger-control` C++, ou usar a biblioteca Python `pydualsense` (MIT, 115+ commits). Implementar do zero custa duas sprints inteiras; FFI do C++ adiciona complexidade de build; `pydualsense` resolve 100% do protocolo HID com licença compatível.

## Decisão
Usar `pydualsense >= 0.7.5` como backend. Interface `IController` (ADR interna) abstrai a dependência para permitir troca futura sem reescrever daemon.

## Consequências
Velocidade de desenvolvimento maior. Bugs upstream são contribuíveis. Se `flok/pydualsense` arquivar, forkamos (MIT permite). Performance a 60Hz é suficiente para gatilhos; casos de 1000Hz (competitivo) podem exigir backend C via cffi no futuro.
