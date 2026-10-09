---
sprint: O-DEGRAU-DO-MEIO-E-A-FRASE-DA-FAIXA-SE-LIGAM-DEPOIS-DA-B9-01
estado: aberta
# ciclo: aberta desde=09/10/2026
# publico: em-casa
# 09/10/2026, leva 1-11: as duas entradas do `_SEM_CAMINHO_HOJE` que o multi-1-14 deixou para a B9 ganham dona. Para a próxima leva.
bancada: true
depois_de:
  - A-PONTE-SE-OTIMIZA-ATE-QUATRO-NO-ULTRA-NUM-ADAPTADOR-01
  - A-FAIXA-DO-TECLADO-SE-ACHA-01
  - A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01
  - AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA-01
  - A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01
  - A-MIRA-DA-CALIBRAR-E-A-MESMA-DAS-OUTRAS-ABAS-01
  - O-SINAL-DE-CADA-CONTROLE-DIZ-SE-ELE-ESTA-LONGE-01
  - TODO-TEXTO-QUE-ABRE-UMA-LINHA-COMECA-COM-MAIUSCULA-01
  - A-LINHA-MODELO-DIZ-O-NOME-DO-JOGADOR-01
  - O-ANALOGICO-VIRTUAL-E-UM-SO-COM-O-LADO-ESCOLHIDO-01
  - O-CARTAO-DO-EXTERNO-MOSTRA-O-QUE-ELA-DECLAROU-01
  - O-CODIGO-SEM-NARRADOR-02
  - A-08-MOSTRA-O-DESENHO-DO-CONTROLE-E-O-HUB-PERGUNTA-A-ENTRADA-01
  - A-LINHA-DO-EXTERNO-VOLTA-AOS-30-PX-E-A-COR-FORA-DA-LISTA-SE-ESCOLHE-01
  - A-PONTE-PAUSADA-DIZ-A-VERDADE-NA-CONEXOES-01
  - A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01
  - AS-QUATRO-LINHAS-DA-08-SEM-DONO-GANHAM-DONO-OU-SAEM-DO-DESENHO-01
  - O-NOME-DO-JOGADOR-TEM-UM-DONO-SO-01
  - O-SINAL-SE-MEDE-EM-DOIS-ADAPTADORES-01
posse:
  O-DEGRAU-DO-MEIO-E-A-FRASE-DA-FAIXA-SE-LIGAM-DEPOIS-DA-B9-01:
    - src/hefesto_dualsense4unix/integrations/radio_da_mesa.py
    - src/hefesto_dualsense4unix/daemon/subsystems/governador_do_radio.py
    - src/hefesto_dualsense4unix/integrations/receptor_sem_fio.py
    - src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py
    - tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py
    - tests/unit/test_o_degrau_do_meio_e_a_frase_da_faixa_se_ligam.py
cria:
  - tests/unit/test_o_degrau_do_meio_e_a_frase_da_faixa_se_ligam.py
---

# O degrau do meio e a frase da faixa se ligam depois da B9

## O que se mediu (09/10/2026, no código)

O multi-1-14 deixou dois saberes sem caminho no produto, listados no `_SEM_CAMINHO_HOJE` do
`tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`:

- `integrations/radio_da_mesa.py::ordem_de_ceder`: o degrau do meio (ceder a TAXA da ponte de
  vibração antes de cortá-la inteira) existe, mas `DEGRAU_DO_MEIO_LIGADO` nasce `False` e o
  governador do rádio ainda corta a ponte inteira sem chamar esta ordem.
- `integrations/receptor_sem_fio.py::frase_do_fim`: a frase da causa medida quando a procura da
  faixa termina sem faixa. Só o ensaio `scripts/ensaios/a_faixa_do_receptor.py` a lê; a 08 ainda
  mostra a frase genérica `FAIXA_NAO_ENCONTRADA` em `_andar_a_descoberta`.

## A causa

Os dois esperam a mesma prova: a bancada B9 com ela. O degrau depende de o firmware tocar os dois
blocos de háptica por relatório (`scripts/ensaios/a_ponte_com_dois_quadros.py`); a frase depende
de as causas medidas (`CAUSA_SALTA`, `CAUSA_SEM_MUDANCA`, `CAUSA_SEM_MAPA`) se confirmarem no
aparelho dela.

## A cura na origem

- Com a B9 dizendo que o firmware toca os dois blocos: `DEGRAU_DO_MEIO_LIGADO` liga, e o
  `governador_do_radio` decide pela `ordem_de_ceder` (a taxa cede antes da ponte inteira), em
  P1 a P4, cabo e rádio.
- Com a B9 confirmando as causas: a 08 troca a frase genérica pela `frase_do_fim` da descoberta,
  que é mudança visível e passa pelo desenho antes do `--publicar`.
- As duas entradas saem do `_SEM_CAMINHO_HOJE` no mesmo commit.

## Como se prova

- Régua: com o degrau ligado, o governador sob pressão cede a taxa antes de cortar a ponte; com a
  descoberta terminando sem faixa e causa medida, a 08 mostra a frase da causa.
- **Mordida:** devolvido o corte inteiro direto no governador (ou a frase genérica na 08), a régua
  reprova; e `portao_a_casa_sabe_e_o_produto_nao_faz` reprova se as entradas ficarem com o caminho
  já ligado.
- Se a B9 disser que o firmware NÃO toca os dois blocos, o degrau sai do código e a entrada sai
  da lista pela saída do saber, não pela ligação.
