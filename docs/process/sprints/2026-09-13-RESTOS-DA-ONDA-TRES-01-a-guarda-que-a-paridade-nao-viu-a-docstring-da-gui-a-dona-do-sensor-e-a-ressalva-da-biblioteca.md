---
sprint: RESTOS-DA-ONDA-TRES-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  RESTOS-DA-ONDA-TRES-01:
    - src/hefesto_dualsense4unix/broker/hidraw_broker.py
    - tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py
    - scripts/check_ate_onde_a_prova_chegou.py
    - tests/unit/test_portao_a_quinta_pergunta_morde.py
    - docs/data/paridade-gtk-html.csv
    - docs/data/mapa-controles.csv
    - docs/data/LEIA-PRIMEIRO.md
    - html/specs.html
    - docs/process/2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md
    - docs/process/sprints/2026-09-13-RESTOS-DA-ONDA-TRES-01-a-guarda-que-a-paridade-nao-viu-a-docstring-da-gui-a-dona-do-sensor-e-a-ressalva-da-biblioteca.md
cria: []
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/
  - src/hefesto_dualsense4unix/daemon/
  - src/hefesto_dualsense4unix/profiles/
  - src/hefesto_dualsense4unix/integrations/
---

# RESTOS-DA-ONDA-TRES-01 — a guarda que a paridade não viu, a docstring da GUI, a dona do sensor e a ressalva da biblioteca

Os validadores da onda 3 da [terceira lista](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)
deixaram quatro achados fora da posse das sprints deles. Nenhum muda a tela, e
nenhum toca o daemon. São os fatos errados que ficaram: *"provou que uma info tá
errada, substituímos ela pela certa em todos os lugares"* (a regra dela de
21/08, no contrato da casa).

## §E — O que os validadores mediram

1. **A docstring que ainda diz «a GUI».**
   `broker/hidraw_broker.physical_nodes_exposure` diz que «a GUI e o doctor.sh
   passam a consultar». Desde a
   [RESTOS-DA-ONDA-DOIS-01](2026-09-13-RESTOS-DA-ONDA-DOIS-01-o-alto-falante-sem-endereco-o-touchpad-na-troca-a-varredura-sem-leitor-e-o-numero-do-parar.md),
   a aba 07 não varre mais o hidraw, e só o `doctor.sh` consulta. A mesma sprint
   declarou a função em `_NAO_E_PROMESSA` no
   `portao_a_casa_sabe_e_o_produto_nao_faz.py`, por causa dessa promessa.
2. **A guarda que a paridade não viu.** A linha da aba 02 «Guarda "sem endereço"
   — desligar o som do card quando não há MAC» continua `FALTA_NO_HTML` e cita o
   endereço `som-sem-endereco`, que não existe mais no código. A RESTOS-DA-ONDA-DOIS-01
   fez a guarda: a moldura do alto-falante de um controle sem endereço ganha
   `data-apagado="sem-alvo"` (`a02_controles`), apaga no WebKit e recusa o gesto.
3. **A dona da linha do sensor.** Em `scripts/check_ate_onde_a_prova_chegou.py`,
   a linha `sensor` diz na razão que o que falta é da MESA-DE-QUATRO-01, e a
   coluna da dona continua na SENSORES-NO-JOGO-01, que está feita. A SENSORES-NO-JOGO-03
   não trocou porque a posse dela mandava não mexer no veredito.
4. **A ressalva da biblioteca.** As células `movimento.giroscopio.jogo@dualsense`
   e `movimento.acelerometro.jogo@dualsense` do mapa não trazem o fato medido
   pela [SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md)
   (§1): o dado chega ao vpad, e o jogo só o recebe se a biblioteca dele ler o nó
   de movimento. A nota da
   [MESA-DE-QUATRO-01](2026-09-06-MESA-DE-QUATRO-01-quatro-dualsense-por-cabo-e-por-radio-com-ela.md)
   sobre essas células diz como a bancada confere a biblioteca do jogo.

## §D — O que está decidido

1. Fato errado se substitui em todos os lugares; decisão medida ganha nota datada.
2. Veredito de célula do mapa não muda sem medição: a ressalva entra na coluna de
   observação, datada, e os vereditos ficam.
3. Nenhum script novo, nenhuma mudança de tela, nenhum código de produto além da
   docstring.

## §I — A implementação

1. **A docstring:** diz quem consulta hoje (só o `doctor.sh`). Se, com a promessa
   corrigida, a declaração em `_NAO_E_PROMESSA` deixar de ser necessária, ela sai;
   se continuar, a razão escrita ao lado dela diz a verdade de hoje.
2. **A paridade:** a linha da guarda é medida de novo contra o código dos dois
   lados, com o `html_onde` pelo símbolo da guarda de hoje e o veredito que a
   medição der. A tabela de números do
   [O TERCEIRO NÚMERO](../2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md)
   acompanha a contagem (a regra `numero-publicado` de
   `scripts/check_paridade_gtk_html.py`). Procure na paridade toda outra linha que
   cite `som-sem-endereco` ou o `_steam_input_excecao_status`, que também saiu.
3. **A dona do sensor:** a coluna segue a razão, e a régua da quinta pergunta
   (`test_portao_a_quinta_pergunta_morde.py`) acompanha.
4. **A ressalva:** nota datada nas duas células, com o endereço da SENSORES-NO-JOGO-02
   e da MESA-DE-QUATRO-01. Depois regerar o `html/specs.html`
   (`scripts/gerar-mapa.py`) e publicar os números
   (`scripts/check_paridade_transporte.py --leia-primeiro --escrever`).
5. **As citações de linha das planilhas:** o roteiro da CITACOES-DAS-PLANILHAS-01
   mora no rascunho de quem coordena, que o roda de novo na costura. Não reaponte à
   mão o que você não deslocou.

## §V — A prova

* `check_paridade_gtk_html.py` verde com a contagem nova; **mordida:** devolver a
  tabela do TERCEIRO NÚMERO à contagem velha reprova pelo `numero-publicado`.
* `test_portao_a_quinta_pergunta_morde.py` verde; **mordida:** devolver a dona
  velha reprova (se não reprovar, a régua ganha o caso).
* `gerar-mapa.py --check` e `check_paridade_transporte.py --leia-primeiro` verdes;
  **mordida:** a célula com a ressalva e o `specs.html` velho reprova.
* `portao_a_casa_sabe_e_o_produto_nao_faz.py` verde depois do §I.1.
* Os portões até todos verdes.

## §0 — O processo

Os achados vieram medidos pelas validações da onda 3 → IMPLEMENTA → VALIDA/CORRIGE.
