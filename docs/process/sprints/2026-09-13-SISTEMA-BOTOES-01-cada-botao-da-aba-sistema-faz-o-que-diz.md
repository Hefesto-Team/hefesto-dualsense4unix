---
sprint: SISTEMA-BOTOES-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  SISTEMA-BOTOES-01:
    - src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py
    - src/hefesto_dualsense4unix/interface/aba09.py
    - src/hefesto_dualsense4unix/gui/aba_sistema.py
    - src/hefesto_dualsense4unix/integrations/storm_doctor.py
    - src/hefesto_dualsense4unix/app/actions/daemon_actions.py
    - docs/data/paridade-gtk-html.csv
    - scripts/check_cabo_bt_perfil_controle.py
    - tests/unit/test_a_09_sistema_fecha_a_paridade.py
    - tests/unit/test_a_09_sistema_sai_do_desenho.py
    - tests/unit/test_a_aba_09_sistema_fecha_as_linhas.py
    - tests/unit/test_o_gesto_devolve_para_a_tela.py
    - tests/unit/test_a_09_sistema_confirma_em_dois_cliques.py
    - tests/unit/test_os_quatro_gestos_da_aba_sistema_que_faltavam.py
    - tests/unit/test_sistema_e_conexoes_perguntam_e_nao_narram.py
    - docs/process/sprints/2026-09-13-SISTEMA-BOTOES-01-cada-botao-da-aba-sistema-faz-o-que-diz.md
cria:
  - tests/unit/test_cada_botao_da_aba_sistema_faz_o_que_diz.py
bancada: false
depois_de:
  # 13/09/2026: a recusa da 09 usa a piscada que a FRASES-E-DICAS-01 cria, e o
  # clique que só arma depende de o piloto não piscar verde — lado dela.
  - FRASES-E-DICAS-01
  # 13/09/2026: a ALTURA-DA-VISTA-01 escreve o mesmo `aba09.py` e é costurada
  # por quem coordena antes da onda 1.
  - ALTURA-DA-VISTA-01
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - scripts/fix_wireplumber_default_source.sh
  - scripts/disable_steam_input.sh
  - src/hefesto_dualsense4unix/integrations/proton_pin.py
  - src/hefesto_dualsense4unix/integrations/steam_launch_options.py
  - src/hefesto_dualsense4unix/daemon/subsystems/plugins.py
  - src/hefesto_dualsense4unix/cli/cmd_plugin.py
  - install.sh
---

# SISTEMA-BOTOES-01 — cada botão da aba Sistema faz o que diz, e funciona

> **ROTA CORRIGIDA — 13/09/2026, depois do estudo.** Esta sprint ABSORVE as §3
> e §4 da
> [TELA-CALADA-04](2026-09-13-TELA-CALADA-04-a-recusa-sem-coluna-o-verde-sem-dono-e-o-painel-que-fala-jargao.md)
> (o painel em repouso sem o diário, e a pergunta que envelhece) — mesmo
> `a09_sistema.py`, mesmo painel — e as duas linhas da aba Sistema que o estudo da
> [FRASES-E-DICAS-01](2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md)
> achou. Corre DEPOIS da FRASES-E-DICAS-01.

A palavra dela está no índice: *«não sei se nossos botões da aba sistema fazem o
que deveriam fazer de fato e se funcionam»*.

## §E — Os catorze gestos, medidos

Piloto oculto com dublê em tudo que muda a máquina (systemctl, ponte, Steam,
Proton, camadas, perfil, scripts de conserto), sete réguas pontuais da 09 (150
verdes) e leituras só-de-leitura da máquina dela. Os 159 perfis dela saíram
idênticos por md5.

| gesto | veredito | o que falha |
| --- | --- | --- |
| `perfil-da-mesa`, `autostart`, `reiniciar`, `ver-detalhes`, `corrigir-modo`, `retomar` | funcionam | — |
| `atualizar` | em parte | a recusa com o serviço mudo não chega à tela |
| `desligar`, `restaurar-de-fabrica` | em parte | o clique 1 arma SEM a pergunta que o `title` promete, e pisca verde |
| `aplicar-aos-jogos` | em parte | a pergunta chega; a recusa do clique 2 é muda |
| `procurar-camadas` | em parte | a recusa com jogo aberto é muda |
| `refazer-consertos` | em parte, e faz o que não diz | nenhum script põe a linha de inicialização nos jogos, que o `title` promete; o conserto da Steam adia com ela aberta; e o `--install` do `scripts/fix_wireplumber_default_source.sh` apaga a marca do gesto do microfone, reelege a fonte padrão e reinicia o WirePlumber da sessão sem dizer |
| `refazer-proton` | não funciona no uso real | a Steam aberta só é conferida no clique 2, depois de armar e piscar verde; a recusa é muda |
| `ver-plugins` | não tem como funcionar | os plugins vêm desligados por padrão e nenhuma tela os liga |

**A causa que atravessa:** a 09 não tem `[data-controle]` nem faixa, e toda
recusa ia só ao diário — a FRASES-E-DICAS-01 dá a ela a piscada de recusa.

**Da TELA-CALADA-04, medido pela triagem de 13/09:** `_repouso_do_painel` chama
`_systemctl_status_text` de `daemon_actions.py`, que roda `status --no-pager`
sem `-n 0` e emenda o diário do daemon, com `uniq=`; e `_PAINEL` só é limpo no
ramo confirmado, logo a pergunta vencida fica no painel.

**Da FRASES-E-DICAS-01:** a linha do exame mostra, em texto e em `title`, o «O que
fazer: clique 'Aplicar correções' na aba Sistema.» do doctor — um botão que não
existe com esse nome; e `SEM_COR_LIDA` confessa a cor não lida.

O estudo inteiro fica na pasta do lote `1309-terceira`.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| «Ver os plugins» SAI da aba — o botão, a razão cinza e o gesto; a CLI e o IPC ficam | D-OS-PLUGINS-APARECEM-ONDE-AGEM, dela, 26/08 («Plugins não ganham seção própria»), em `docs/data/decisoes-dela.csv`; o índice: «tirar e enxugar» |
| «Refazer os consertos» deixa de rodar o `--install` do WirePlumber, e o `title` perde as duas promessas que não valem | o próprio script (DROPIN-AMBIGUO-01: «`--install` é o gesto CONTRÁRIO ao de ligar o mic»); a D-12 dela em [AS DEZESSEIS DECISÕES](../2026-09-04-AS-DEZESSEIS-DECISOES-DELA-e-as-sprints-que-nascem.md) |
| O clique 1 de Parar, Restaurar e Proton põe no painel a pergunta: o `title` já publicado mais `CLIQUE_DE_NOVO`; nenhuma palavra nova | os dois cliques são decisão dela de 03/09 (docstring em `a09_sistema.py`); a TELA-CALADA-03: «a pergunta de um gesto em dois tempos fica» |
| O Proton confere a Steam no clique 1 e recusa ali, sem armar | o precedente de `procurar_camadas`: «nada a oferecer, logo nada a armar» |
| A recusa da 09 não ganha canal próprio: é a piscada da FRASES-E-DICAS-01, sem `title` | a §D da FRASES-E-DICAS-01 |
| O «O que fazer» do doctor é cortado NA TELA, lido de `PREFIXO_DA_CURA` no dono; o doctor para de citar botão que não existe | «quando um valor tem dono, a régua pergunta ao dono»; a régua do doctor exige o prefixo na string |

## §I — IMPLEMENTA (o painel primeiro)

1. **O painel em repouso:** sem as linhas do diário — `-n 0` em
   `_systemctl_status_text`, mantendo a assinatura de um argumento (cinco réguas
   a dublam assim). O «Ver detalhes» fica como está.
2. **A pergunta que envelhece:** quando o consentimento vence ou passa a outro
   gesto, a pergunta sai do painel no tique seguinte. Meça antes o preço que a
   TELA-CALADA-03 apontou (o censo das camadas sumir junto) e escolha o caminho
   que não o apaga.
3. **O clique que só arma** devolve `armou` na carga.
4. **Parar, Restaurar e Proton:** o clique 1 escreve a pergunta no painel; o
   clique 2 limpa.
5. **Proton:** Steam aberta → recusa no clique 1, sem armar. A pergunta que lê o
   `config.vdf` sem `proton-pin.conf` (instalação por pacote) vira recusa com a
   frase do dono, nunca exceção.
6. **Consertos:** o `--install` do WirePlumber sai de `CONSERTOS`; o `title`
   enxuga em `aba09.py`; a instrução do `storm_doctor.py` que manda clicar num
   botão que não existe aponta o caminho que existe, ou sai.
7. **«Ver os plugins» sai:** o gerador, `_CINZAS`, o gesto, as listas que o citam,
   `gui/aba_sistema.py`, a paridade (nota datada, nunca apagada) e
   `scripts/check_cabo_bt_perfil_controle.py`.
8. **As duas linhas da FRASES:** `SEM_COR_LIDA` diz só o nome da cor; a linha do
   exame corta texto e `title` em `PREFIXO_DA_CURA`.
9. Regerar e `--publicar 09`.

## §V — VALIDA/CORRIGE — o que morde

* Piloto oculto com dublê: retomar, atualizar (ponte muda), corrigir-modo
  (serviço pelo sistema), refazer-proton (Steam aberta) e aplicar-aos-jogos (jogo
  aberto) vestem a classe de recusa; nenhum `title` ganha a frase.
* Clique 1 de refazer-proton, restaurar-de-fabrica, desligar, refazer-consertos e
  aplicar-aos-jogos: nenhum `hef-deu-certo`; o painel tem o `title` do botão e
  `CLIQUE_DE_NOVO`. **Arrancar → volta o que o estudo mediu, e reprova.**
* Proton com a Steam aberta: o clique 1 recusa, nada fica armado, e a fixação
  não é chamada.
* Consertos: o log das dublês só tem o `--apply-quiet` do vigia da Steam;
  devolver o `--install` → reprova.
* Página publicada: zero `data-gesto="ver-plugins"`; `BOTOES_CINZAS` com
  `retomar` e `reiniciar` só.
* Painel em repouso sem `uniq` e sem linha de diário; pergunta vencida some no
  tique seguinte.
* Fotos da 09 antes e depois; portões verdes; perfis por md5.

## §R — Riscos declarados

* `--publicar 09` leva ao produto QUALQUER divergência pendente da bancada da 09:
  confira antes.
* Sem «Ver os plugins», a lista Avançado fica com três itens: o portão de alturas
  das colunas irmãs pode reclamar.
* Muitos documentos citam `a09_sistema.py` por linha: reapontar por símbolo, por
  último.
* Nenhum gesto contra o real: systemctl, Steam, `config.vdf`, WirePlumber — só
  dublê.

**Só o aparelho responde (MESA-DE-QUATRO-01):** o «Aplicar aos jogos» fechando a
Steam de verdade e repondo os dois jogos que ela citou; Parar, Ativar e Reiniciar
no systemd real; o reinício do WirePlumber no meio de um jogo pelo rádio.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | não se aplica: os gestos são da máquina |
| **no perfil** | «Restaurar de fábrica» mexe no perfil; nada novo vai ao disco |
| **por controle** | não se aplica |
