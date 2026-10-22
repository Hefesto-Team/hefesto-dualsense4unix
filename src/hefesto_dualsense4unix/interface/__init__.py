"""A INTERFACE — as dez abas do desenho dela, vivas, dentro de uma janela GTK.

Mora no pacote porque o wheel só empacota `src/hefesto_dualsense4unix` (01/09/2026).
Produto: `paginas/`, `hefesto_vivo.py`, `pacotes/`, `monta.py`, `mesa_viva.py`, `onde.py`.
Bancada que fica ao lado do que gera: os geradores `abaNN.py`, `olhar.py` e `ver.py`;
as outras réguas e os pilotos de uma aba só moram em `scripts/tela/` (22/10/2026).
Os gestos falam com o daemon por `app/ipc_bridge.py`; a pintura de três abas delega para
`app/telas/vibracao.py`, `app/actions/perfis_web.py` e `interface/sistema.py`.
"""
