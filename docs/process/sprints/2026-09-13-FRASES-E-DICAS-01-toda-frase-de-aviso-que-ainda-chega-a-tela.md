---
sprint: FRASES-E-DICAS-01
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  FRASES-E-DICAS-01:
    - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
    - src/hefesto_dualsense4unix/interface/folha_da_casa.py
    - src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py
    - src/hefesto_dualsense4unix/interface/aba05.py
    - tests/unit/test_a_recusa_chega_ao_cartao.py
    - tests/unit/test_a_tela_nao_narra_o_gesto_que_deu_certo.py
    - tests/unit/test_o_piloto_tem_o_terceiro_lugar_e_a_quarta_porta.py
    - tests/unit/test_o_recado_de_sucesso_pousa_no_cartao.py
    - tests/unit/test_regua_de_tela_a_aba_controles.py
    - tests/unit/test_a_iluminacao_avisa_quantos_receberam_o_desenho.py
    - tests/unit/test_a_aba_05_vibracao_fecha_as_linhas.py
    - tests/unit/test_a_aba_09_sistema_fecha_as_linhas.py
    - tests/unit/test_a_iluminacao_diz_o_numero_certo.py
    - scripts/regua_de_tela.py
    - scripts/ensaios/o_recado_nao_desloca_a_coluna.py
    - scripts/ensaios/a_forca_por_controle_no_webkit.py
    - docs/process/sprints/2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md
cria:
  - tests/unit/test_a_recusa_pisca_no_botao.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/app/ipc_bridge.py
  - src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py
  - src/hefesto_dualsense4unix/integrations/storm_doctor.py
  - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
  - src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py
  - src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py
  - src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py
  - src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py
  - scripts/check_a_tela_nao_confessa.py
---

# FRASES-E-DICAS-01 — a recusa sai da tela, e o número fora diz só o número

> **ESTADO 2026-09-13: feita** — `docs/process/agentes/2026-09-13/FRASES-E-DICAS-01-opus.md`

> **ROTA CORRIGIDA — 13/09/2026, depois do estudo, e ela vence o que vier
> abaixo.** A sprint nasceu uma só; o estudo mediu posse larga demais para um
> agente, e ela se partiu. **Esta é o NÚCLEO:** o canal de recado do piloto e o
> número da aba Iluminação. As dicas e as linhas que avisam nas abas 02, 03, 07 e
> 08 são a [FRASES-E-DICAS-02](2026-09-13-FRASES-E-DICAS-02-as-dicas-e-as-linhas-que-avisam-viram-estado.md);
> as da aba Sistema, a [SISTEMA-BOTOES-01](2026-09-13-SISTEMA-BOTOES-01-cada-botao-da-aba-sistema-faz-o-que-diz.md).
> Esta ABSORVE as §1 e §2 da
> [TELA-CALADA-04](2026-09-13-TELA-CALADA-04-a-recusa-sem-coluna-o-verde-sem-dono-e-o-painel-que-fala-jargao.md)
> — e desfaz a §1.2 e a §1.3 dela, pela razão da §D.

As palavras dela estão no índice (`2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`):
a frase da Steam *«… Feche a Steam e eu reponho.»* «segue aparecendo nas abas», e
a caixa laranja da aba Gatilhos *«Esse número é maior do que a quantidade de
controles ligados»* «também tem que parar de aparecer».

## §0 — A regra

**Frase de aviso não chega à tela, em nenhuma aba e em nenhuma forma** — recado,
faixa, caixa, dica flutuante, `title`. A tela mostra ESTADO (rótulo curto) e
responde ao clique pelo sinal do botão.

## §E — O que o estudo mediu (13/09, piloto oculto sobre `e7d1dac2`, só leitura)

1. **A caixa da foto é uma RECUSA.** Com um controle só, os números 2, 3 e 4 da
   aba Iluminação ficam `.fora` e continuam clicáveis de propósito. O clique
   levanta a frase de `app/ipc_bridge.py` (`_MOTIVOS_NUMERO`), e o piloto a leva
   de `_recusou_dizendo` a `_depositar` e a `pintar_recados`, que a pousa em
   grade no cartão do P1 por 30 s. Antes da TELA-CALADA-01 ela seguia para a aba
   Gatilhos — é a foto, reproduzida pixel a pixel. **Hoje ela ainda pousa na
   própria aba 04**, laranja, 236 x 46 px.
2. **A mesma frase é dica flutuante** do número fora («Player 2 — Esse número
   é…»), montada no pacote da 04 e cravada nas páginas 04.
3. **O canal é de todos:** 201 `raise RuntimeError` nos pacotes viram caixa no
   cartão da coluna por 30 s.
4. **A frase da Steam** saiu do cartão (TELA-CALADA-02) e continua sendo a recusa
   do «Consertar» da aba 07. Hoje ela cai no chão, porque a 07 não tem coluna;
   **a §1.2 da TELA-CALADA-04 a levaria ao `title`**, e a camada da dica da casa
   mostra todo `title` como caixa flutuante — a frase voltaria.
5. **O que NÃO é aviso, e fica:** o `?` (`.ajuda`), as dicas que dizem o que o
   controle faz, as contagens e os rótulos curtos. Em repouso, zero recado nas dez
   abas.

O estudo inteiro, com a prova de cada linha, fica na pasta do lote
`1309-terceira`, ao lado da integração (fora do git).

## §D — Decisões (quem coordena, por delegação — índice, §0 item 5)

| decisão | base |
| --- | --- |
| A recusa COM coluna também sai do cartão | a caixa da foto é essa, e a palavra dela no índice manda parar; caduca a §1.3 da TELA-CALADA-04 e o contrato de 02/09 no docstring de `_recusou_dizendo` — nota datada, nunca apagada em silêncio |
| O clique recusado responde pela piscada de recusa no botão, sem texto; a frase vai só ao diário `[gesto falhou]` | a §1.1 da TELA-CALADA-04; a escolha dela do campo que pisca (03-Q4, 05/09), citada no docstring de `_deu_certo_dizendo` |
| A frase NÃO vai ao `title` — a §1.2 da TELA-CALADA-04 não se constrói | o §0 desta sprint põe o `title` entre as formas que saem |
| O número fora diz só «Player N» | o cinza `.fora` já é o vocabulário do estado — o comentário do desenho na página 04 publicada: «um segundo cinza seria um segundo vocabulário para o mesmo fato» |
| O clique que só ARMA não pisca verde | a SISTEMA-BOTOES-01 mediu `hef-deu-certo` no «Confirma?» de cinco botões; o pacote diz `armou` na carga (lado da SISTEMA), e o piloto não pisca (lado daqui) |

## §I — IMPLEMENTA

1. `_recusou_dizendo` para de depositar; o `[gesto falhou] …` do diário fica.
   `voltouDoVoo(n, false)` acende uma classe de RECUSA — ela mora em
   `folha_da_casa.py`, ao lado da verde —, com a duração `MS_DA_PISCADA` e a cor
   de aviso da paleta. Sem texto, com coluna ou sem.
2. Sai o que servia só ao recado, cada contrato com nota datada: `pintar_recados`,
   os estilos do recado (tarja e grade), `COR_DO_SUCESSO`, `_recados`,
   `_recados_para_a_tela`, `SEGUNDOS_DO_RECADO` e `SEGUNDOS_DO_RECADO_DE_SUCESSO`,
   e o depósito de `_a_pagina_morreu` (passa ao diário). **Antes de apagar, meça
   quem ainda lê** — consumidor que sobrar é achado, não entulho.
3. `_gesto`: pisca verde só quando aplicou e a carga não traz `armou`.
4. A faixa `data-hef-recados="sucesso"` da aba 05 sai de `aba05.py`, com a
   autoconferência do gerador. Regerar e `--publicar 05`.
5. No pacote da 04, a dica do número fora é «Player N» e a função que colava a
   frase sai. A dica do tom tomado («já está neste tom — duas peças nunca ficam da
   mesma cor») fica só com o nome do tom. `_MOTIVOS_NUMERO` fica na ponte: é a
   recusa, e vai ao diário. Regerar e `--publicar 04`.
6. As réguas que cobram o canal mudam de contrato **com data e com a citação
   dela** (o índice, a foto da caixa), nunca apagadas.

## §V — VALIDA/CORRIGE — o que morde

* Piloto `--oculta` (`HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, cópia dos
  perfis antes e md5 depois), recusa dublada em gesto COM coluna (`player` da 04,
  `mudo` da 02) e SEM coluna (o cadeado da 01): zero `.hef-recado`; a frase
  ausente de `body.textContent`, de todo `data-hef-dica` e de todo `title`; o
  botão veste a classe de recusa e a perde em `MS_DA_PISCADA`; `[gesto falhou]`
  no stderr. **Devolver o `_depositar` → reprova.**
* Mouseover no `.fora` da 04: `#hef-dica` diz exatamente «Player 2». Devolver a
  frase → reprova.
* A página 05 publicada não declara `data-hef-recados`.
* Carga com `armou`: o botão não veste `hef-deu-certo`. Arrancar → reprova.
* Fotos da 04 e da 05 antes e depois; `scripts/check_o_desenho_aprovado.py` e
  portões verdes.

## §R — Riscos declarados

* Uma recusa que pede um gesto dela («feche o jogo antes…») passa a responder só
  com a piscada. É a ordem dela; a frase fica no diário.
* `scripts/check_a_tela_nao_confessa.py` passa a ler um canal que não chega à
  tela: não apagar, anotar.
* As páginas 04 e 05 também mudam em outras sprints desta leva: **regerar, nunca
  mesclar à mão** — quem coordena regera as dez na costura.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | não se aplica: é a tela |
| **no perfil** | nada vai ao disco |
| **por controle** | a recusa pisca no botão do controle em que nasceu; nenhum cartão ganha texto |
