"""A INTERFACE — as dez abas do desenho dela, vivas, dentro de uma janela GTK.

ELA MUDOU PARA CÁ EM 01/09/2026, e a razão é uma só: o wheel empacota
`packages = ["src/hefesto_dualsense4unix"]`, e nada fora dali entra. Enquanto as
páginas viviam em `layout/`, **quem instalasse o Hefesto não recebia a
interface** — ela só existia na árvore de quem a desenvolvia. Foi o que a
auditoria das dez ondas MIGRA mediu, e o que ela mandou desfazer com estas
palavras: *"preciso do produto completo"*.

O QUE MORA AQUI, e a divisão é entre PRODUTO e BANCADA:

    paginas/            as dez abas + as avulsas — o que o WebView carrega
    hefesto_vivo.py     o piloto: uma janela, as dez, pintadas pelo daemon
    pacotes/            um pacote por aba — o que pinta e o que os botões fazem
    monta.py            o esqueleto compartilhado das dez
    mesa_viva.py        do daemon até o desenho, sem GTK e sem escrever
    onde.py             o dono dos dois caminhos: a bancada e o publicado

    abaNN.py            os GERADORES — bancada. Só quem edita o desenho os roda.
    regua*.py, olhar.py, casamento.py    as réguas — bancada.

Os de bancada vêm junto no pacote por ora, e é uma escolha: eles são pequenos
(dezenas de KB contra os 2,5 MB das páginas) e mantê-los ao lado do que geram é
o que impede o desenho e o gerador de divergirem calados — que é o defeito que
matou a pasta `novo-layout/` em 31/08.

NADA AQUI REESCREVE O PRODUTO. Os gestos falam com o daemon pelo
`app/ipc_bridge.py`, e a pintura de três abas delega para as camadas de tela que
já existiam e ninguém chamava (`app/telas/vibracao.py`,
`app/actions/perfis_web.py`, `gui/aba_sistema.py`). O que saiu foi a JANELA
GTK — os 74 handlers de `app/actions/` continuam sendo o motor.
"""
