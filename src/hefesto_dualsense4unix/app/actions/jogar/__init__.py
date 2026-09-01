"""A aba **Jogar** da interface nova — o que o produto sabe responder por ela.

Este pacote é o lado PURO da aba: nada de GTK, nada de WebKit, nada de disco
fora do que se lhe entrega. Quem hospeda a página é o piloto
(``src/hefesto_dualsense4unix/interface/jogar_vivo.py``); quem sabe **o que a página deve
dizer** é :mod:`~hefesto_dualsense4unix.app.actions.jogar.painel`.

A divisão não é estética. A aba Jogar tem, no desenho aprovado, três coisas que
o produto de hoje **não** sabe responder — e a diferença entre "não sei" e um
número plausível é a diferença entre uma tela honesta e uma que ela vai
acreditar. Essa fronteira mora em ``painel.py``, escrita, e não em comentário de
piloto que não viaja em worktree.
"""
