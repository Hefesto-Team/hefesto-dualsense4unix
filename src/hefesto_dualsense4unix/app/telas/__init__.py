"""Os adaptadores das abas da interface nova — um por aba, e nada de janela.

A interface nova é o mockup aprovado rodando num ``WebKit2.WebView`` dentro de
uma janela GTK3 (``D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK``). A
janela, as duas pontes e a guarda de carga são de TODAS as abas e moram em
``hefesto_dualsense4unix.gui.ponte_da_tela``. O que muda de aba para aba é o
**adaptador**: o que o Python manda para aquela tela, o que ela manda de volta,
e o casamento com o DOM dela.

Cada módulo daqui é **puro**: sem ``gi``, sem widget, sem IPC no import. É o que
permite provar o pacote de pintura sem abrir uma janela — e é a metade que a
régua de tela não alcança, porque ela mede o DOM e não a conta que o alimenta.

A pasta é declarada por escrito na sprint ``MIGRA-VIBRACAO-01``
(``cria: src/hefesto_dualsense4unix/app/telas/vibracao.py``).
"""
