---
sprint: RESTOS-DA-ONDA-DOIS-01
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  RESTOS-DA-ONDA-DOIS-01:
    - src/hefesto_dualsense4unix/interface/aba02.py
    - src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py
    - src/hefesto_dualsense4unix/interface/aba06.py
    - src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py
    - src/hefesto_dualsense4unix/app/actions/emulation_actions.py
    - src/hefesto_dualsense4unix/interface/aba09.py
    - tests/unit/test_o_cartao_diz_se_o_som_tem_para_onde_ir.py
    - tests/unit/test_as_seis_linhas_fora_da_troca_ficam_apagadas.py
    - tests/unit/test_steam_input_d33_nomeia_o_jogo.py
    - docs/process/sprints/2026-09-13-RESTOS-DA-ONDA-DOIS-01-o-alto-falante-sem-endereco-o-touchpad-na-troca-a-varredura-sem-leitor-e-o-numero-do-parar.md
cria:
  - tests/unit/test_os_restos_da_onda_dois.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/interface/topo.html
  - docs/data/paridade-gtk-html.csv
  - docs/data/mapa-controles.csv
  - html/specs.html
---

# RESTOS-DA-ONDA-DOIS-01 — o alto-falante sem endereço, o touchpad na troca, a varredura sem leitor e o número do Parar

> **ESTADO 2026-09-13: feita** — [a entrega](../agentes/2026-09-13/RESTOS-DA-ONDA-DOIS-01-opus.md).

Nasceu na costura da onda 2 (13/09/2026). São quatro achados que as validações
mediram e deixaram abertos só por posse. A regra é a do
[índice](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md): nada de botão novo, nada
de frase de aviso, mexer o mínimo.

## §E — O que as validações mediram

| onde | o defeito | quem achou |
| --- | --- | --- |
| 02, a moldura do alto-falante | a guarda de controle sem endereço nunca acende no WebKit: as regras de `aba02.py` casam `.moldura[data-bloco="alto-falante"][title]`, e a camada da dica (TOOLTIP-C1) leva todo `title` para `data-hef-dica`. O deslizante fica aceso para um controle que não tem para onde mandar o som | a validação da MIC-SEM-FONTE-01 ([entrega](../agentes/2026-09-13/MIC-SEM-FONTE-01-opus.md)), confirmado no DOM e anterior à sprint |
| 06, a tela «Trocar os botões» | as três linhas do touchpad carregam a marca «não dispara», cuja dica diz «A escolha fica guardada.»; na troca a lista ao lado está apagada e não guarda escolha nenhuma. A célula do botão é a mesma nas Definições, onde a frase é verdadeira | a validação da F1-REMAPEAR-02 ([entrega](../agentes/2026-09-13/F1-REMAPEAR-02-opus.md)) |
| 07, o cartão da Steam | `a07_lancadores.pacote` ainda chama `_steam_input_excecao_status`, que varre os hidraw para achar o `efetiva`, e o `efetiva` não chega mais à tela | a validação da FRASES-E-DICAS-03 ([entrega](../agentes/2026-09-13/FRASES-E-DICAS-03-opus.md)) |
| 09, o «Parar o serviço» | o `title` diz «os 2 viram gamepads comuns do Linux», com o número cravado pelo gerador (`N = len(CONECTADOS)`), e desde a SISTEMA-BOTOES-01 esse `title` é a pergunta escrita no painel no primeiro clique. Com um, três ou quatro controles o número está errado | a validação da SISTEMA-BOTOES-01 ([entrega](../agentes/2026-09-13/SISTEMA-BOTOES-01-opus.md)) |

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| A guarda do alto-falante passa a casar um endereço que a camada da dica não consome, na forma que a MIC-SEM-FONTE-01 deu ao microfone (`data-apagado`), sem frase nova | a ROTA CORRIGIDA da MIC-SEM-FONTE-01 e o §0 do índice |
| Na tela da troca, as três linhas do touchpad perdem a marca «não dispara»; nas Definições ela fica como está | a marca é verdade só onde a escolha é guardada; tirar pode, e é o mínimo (§0 do índice) |
| A varredura sai da 07 se nada vivo ler o `efetiva`; a assinatura de `markup_status_steam_input` enxuga junto se só réguas passarem o valor | a regra da casa para código sem leitor, e o §0 do índice (enxugar) |
| O `title` do Parar deixa de cravar o número: «os controles viram gamepads comuns do Linux» | fato errado se substitui (regra da casa); nenhuma palavra nova além de trocar o número pelo substantivo que o próprio texto já usa |

## §I — IMPLEMENTA

1. `aba02.py` e `a02_controles.py`: a moldura do alto-falante recebe o endereço
   próprio (o mesmo molde do `mic-apagado`), e as regras de opacidade e de
   cursor passam a casar esse endereço. Regere e publique a 02.
2. `aba06.py`: a tabela da troca desenha as três linhas do touchpad sem a
   `MARCA_DO_TOUCHPAD`; a tabela das Definições continua com ela. A
   autoconferência do gerador passa a conferir as duas. Regere e publique a 06.
3. `a07_lancadores.py` e `emulation_actions.py`: medir quem lê o `efetiva`.
   Sem leitor vivo, a 07 para de chamar a varredura e a função enxuga; as
   réguas que passam o valor ganham nota datada.
4. `aba09.py`: o `title` do Parar troca «os {N}» por «os controles». Regere e
   publique a 09.
5. A régua nova (`tests/unit/test_os_restos_da_onda_dois.py`) cobre os quatro:
   a guarda do alto-falante acende no WebKit com o controle sem endereço; a
   marca não aparece na troca e aparece nas Definições; a 07 não abre hidraw
   no tique; o `title` publicado do Parar não tem dígito.

## §V — Prova

* Piloto oculto (`HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, perfis copiados
  antes): foto da 02 com um controle sem endereço dublado (o alto-falante
  apagado) e da tela «Trocar os botões» da 06; clique no Parar da 09 com o
  `systemctl` dublado, lendo a pergunta no painel.
* Mordidas: o seletor antigo de volta na 02; a marca de volta na troca; a
  varredura de volta na 07; o número de volta no Parar. Cada uma reprova a sua
  régua, e a devolução sai idêntica no `git diff`.
* Contagem de `<button` e `data-gesto` nas páginas 02, 06 e 09, antes e depois:
  nenhum botão novo.

## §R — O preço

A tela da troca deixa de dizer que o clique do touchpad não dispara; a lista
apagada ao lado já diz que ali não se troca nada.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | o alto-falante sem endereço é o controle que não tem para onde mandar o som, nos dois transportes |
| **no perfil** | a troca e o Parar não mudam de perfil |
| **por controle** | a guarda do alto-falante é por cartão; o Parar é da máquina |
