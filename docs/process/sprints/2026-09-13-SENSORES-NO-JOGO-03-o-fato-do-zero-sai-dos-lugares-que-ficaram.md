---
sprint: SENSORES-NO-JOGO-03
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  SENSORES-NO-JOGO-03:
    - src/hefesto_dualsense4unix/daemon/sensor_hub.py
    - src/hefesto_dualsense4unix/daemon/ipc_handlers.py
    - scripts/check_ate_onde_a_prova_chegou.py
    - docs/process/agentes/2026-09-04/ONDA1-D3.md
    - docs/process/agentes/2026-09-11/AUDITORIA-SOM-GIRO-01-opus.md
    - docs/process/sprints/2026-09-11-AUDITORIA-SOM-GIRO-01-todas-as-features-por-controle-e-dentro-do-jogo.md
    - docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md
    - docs/process/sprints/2026-09-05-ONDA-CINCO-INDICE.md
    - docs/process/sprints/2026-09-13-SENSORES-NO-JOGO-03-o-fato-do-zero-sai-dos-lugares-que-ficaram.md
cria: []
bancada: false
depois_de: []
nao_toca:
  - docs/data/mapa-controles.csv
  - html/specs.html
  - docs/data/paridade-gtk-html.csv
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
---

# SENSORES-NO-JOGO-03 — o fato do zero sai dos lugares que ficaram

> **ESTADO 2026-09-13: feita** — a mesma frase certa entrou nos oito lugares:
> as docstrings de `_reconciliar_grabs` e do `sensor.set` com o mesmo número de
> linhas (641 e 6950), a razão do `sensor` na régua da quinta pergunta com o
> veredito igual, e os três documentos vivos; as duas entregas ganharam a nota
> datada no topo. A busca das formas antigas foi de 23 achados em 12 arquivos a
> 14 em 6, todos registro ou nota datada. As duas mordidas reprovaram. A entrega
> está em `docs/process/agentes/2026-09-13/SENSORES-NO-JOGO-03-opus.md`.

Nasceu na costura da onda 2 (13/09/2026). A
[SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md)
substituiu, na posse dela, o fato de que o jogo não recebe o giroscópio em Modo
Virtual e de que o SDL não lê o nó «Motion Sensors». A validação contou oito
lugares fora da posse que ainda o afirmam
([entrega](../agentes/2026-09-13/SENSORES-NO-JOGO-02-opus.md)). A regra da casa:
fato errado sai de TODOS os lugares onde aparece.

## §E — Onde o fato ficou

| arquivo | o que afirma |
| --- | --- |
| `src/hefesto_dualsense4unix/daemon/sensor_hub.py` | a docstring de `_reconciliar_grabs`: o SDL não lê o nó «Motion Sensors» |
| `src/hefesto_dualsense4unix/daemon/ipc_handlers.py` | a docstring do `sensor.set`: o SDL não lê o nó, e em Virtual lê o giro pelo hidraw do vpad |
| `scripts/check_ate_onde_a_prova_chegou.py` | a frente `sensor`: a hipótese de que em Virtual o jogo não recebe o giroscópio |
| `docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md` | §3.3: o SDL não enumera aquele nó |
| `docs/process/sprints/2026-09-05-ONDA-CINCO-INDICE.md` | o item do giroscópio sob a máscara Xbox |
| `docs/process/sprints/2026-09-11-AUDITORIA-SOM-GIRO-01-todas-as-features-por-controle-e-dentro-do-jogo.md` | §1 |
| `docs/process/agentes/2026-09-04/ONDA1-D3.md` e `docs/process/agentes/2026-09-11/AUDITORIA-SOM-GIRO-01-opus.md` | entregas de agente que repetem o fato |

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| Docstring, script e documento vivo trocam o fato pelo certo, com o endereço da biblioteca | fato errado se substitui em todos os lugares (regra da casa) |
| Entrega de agente é registro do que o agente viu: ganha uma nota datada no topo apontando o fato substituído, e o corpo fica | não se apaga decisão medida; a entrega é o registro dela |
| Docstring de código muda com o MESMO número de linhas | as planilhas e os comentários citam esses arquivos por linha, e a CITACOES-DAS-PLANILHAS-01 corre na mesma onda |

## §I — IMPLEMENTA

1. O fato certo, em uma frase, igual nos oito lugares: o zero em Modo Virtual
   era da libSDL2 2.30.0 do sistema; nas bibliotecas dos runtimes da Steam o
   vpad expõe os dois sensores, e o SDL pareia o nó «Motion Sensors» pelo `uniq`
   (a tabela está na SENSORES-NO-JOGO-02, §1).
2. `sensor_hub.py` e `ipc_handlers.py`: só a docstring, com o mesmo número de
   linhas.
3. `check_ate_onde_a_prova_chegou.py`: a frente `sensor` troca a hipótese pelo
   fato medido e pelo que falta medir no jogo (MESA-DE-QUATRO-01), sem mudar o
   veredito que o script calcula.
4. Os três documentos vivos trocam o fato; as duas entregas ganham a nota.
5. A busca pelas formas antigas (a lista está na §V da SENSORES-NO-JOGO-02)
   volta vazia nos arquivos versionados, fora as notas datadas de que o fato
   caiu.

## §V — Prova

* A busca da §I.5, antes e depois, com a contagem por arquivo.
* `scripts/validar-citacoes-de-linha.py --all` e o portão `citacoes-no-codigo`
  verdes; `git diff --stat` dos dois arquivos de código com o mesmo número de
  linhas.
* A tela não muda: nenhuma foto.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** / **no perfil** / **por controle** | não se aplica: a sprint só troca um fato em texto |
