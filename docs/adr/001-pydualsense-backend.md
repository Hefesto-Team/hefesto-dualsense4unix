# ADR-001: `pydualsense` como backend HID

## Contexto
Três caminhos possíveis: implementar protocolo HID do zero, portar `trigger-control` C++, ou usar a biblioteca Python `pydualsense` (MIT, 115+ commits). Implementar do zero custa duas sprints inteiras; FFI do C++ adiciona complexidade de build; `pydualsense` resolve 100% do protocolo HID com licença compatível.

## Decisão
Usar `pydualsense >= 0.7.5` como backend. Interface `IController` (ADR interna) abstrai a dependência para permitir troca futura sem reescrever daemon.

## Consequências
Velocidade de desenvolvimento maior. Bugs upstream são contribuíveis. Se `flok/pydualsense` arquivar, forkamos (MIT permite). Performance a 60Hz é suficiente para gatilhos; casos de 1000Hz (competitivo) podem exigir backend C via cffi no futuro.
