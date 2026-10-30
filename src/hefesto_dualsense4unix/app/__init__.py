"""O MOTOR do Hefesto - DualSense4Unix: o que a tela chama, sem a tela.

A JANELA GTK SAIU EM 06/09/2026, e este pacote NÃO saiu com a janela. Decisão de produto
(`D-0609-GTK-LEVA-INTEIRA`): reaproveitar o que existia no GTK e não apontar
mais nada para lá, e sim para o HTML. O que morreu foi `app/app.py`
(o `HefestoApp`, que montava a janela) e `app/main.py` (o entry point da janela).

O que fica é o motor que a interface nova chama a cada tique: `app/actions/`
(os 74 handlers), `app/widgets/`, `app/telas/`, o `app/ipc_bridge.py` e o
`app/draft_config.py`. `app/arranque.py` guarda o que se acerta no AMBIENTE
antes de a primeira janela nascer, e veio do topo de `app/main.py`.
"""
