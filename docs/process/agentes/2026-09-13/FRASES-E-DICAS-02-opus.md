# FRASES-E-DICAS-02 — as dicas e as linhas que avisam viram estado (IMPLEMENTA, opus)

Sprint: [FRASES-E-DICAS-02](../../sprints/2026-09-13-FRASES-E-DICAS-02-as-dicas-e-as-linhas-que-avisam-viram-estado.md)
· branch `voo/FRASES-E-DICAS-02-opus` · base `249af1f6` · cura `6cd24565`.

## O que mudou

Medido no piloto oculto (`--oculta`, `sem_cor`, `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`),
antes e depois, com o daemon vivo dela:

| onde | antes | depois |
| --- | --- | --- |
| 08, dica do botão da luz | «Atenção: outro programa está segurando controle agora… Feche-o antes para o gesto valer.» | só o que o botão faz. `AVISO_DA_MESA_SUJA` saiu, e com ela a sonda que a sustentava: `_pergunta_da_mesa`/`_perguntar_pela_mesa` no painel e `_mesa_suja` no pacote, que varria processos a cada 2 s |
| 08, contagem do desenho | `confissao-dica` com «O que eu não consegui conferir neste desenho: …» | «Sem conferir neste desenho: uma coisa.» — `ROTULO_DA_CONTA`, sem dica |
| 08, coluna da ordem | imperativo com `?`, «Ganho esperado: Não medi o ganho nesta máquina. [derivado da conta]», `+1` e o cartão «O que fazer: Abra…» | ordem com destino: só o de→para, com o `+N`; sem ordem: a frase do dono («Nenhuma mudança recomendada agora.»); ordem sem destino: nada |
| fita das dez abas, chip da 03, cravado da 08 | «a cor do plástico deste controle não foi lida» | o nome, ou nenhuma dica |
| 02, dica do canal do alto-falante | «O canal de áudio deste controle está SUSPENSO no PipeWire… medido: …» | «Canal de áudio dormindo» (ou «acordado») |
| 07, cartão da Steam | não achei · erro de leitura · Steam Input ligado com os nomes e o próximo ciclo | «Fora dos caminhos conhecidos» · «Biblioteca da Steam ilegível» · «Ligado em N jogo(s)» / «Ligado no ajuste global da Steam» |

Nenhum botão novo, nada gravado em disco. A página 08 foi regerada por
`src/hefesto_dualsense4unix/interface/aba08.py` e publicada com
`scripts/check_o_desenho_aprovado.py --publicar 08` («OK: o produto não está atrás do desenho dela sem dizer por quê.»).

**AS BASES.** A §D da sprint (quem coordena, por delegação) e as palavras dela de
13/09 em `docs/process/sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md` — §0.4:
«Nada de botão novo. Tirar e enxugar pode; mexer o mínimo.» A §D derruba as
decisões [03] (cartão de cura) e [04] (selo de procedência) de
`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`, que eram
decisões de coordenação e não dela; a [07] (`+N`) fica, junto do de→para.

**O QUE SAIU DA COLUNA NÃO SE PERDEU.** O `?` da linha do exame
(`a08_conexoes._dica_da_linha`) já trazia «Por que importa», «Ganho esperado» e
«O que fazer: <ação>»; «O que eu vi aqui» é o texto da própria linha. Provado em
`test_o_card_traz_as_duas_frases_da_ordem_no_interrogacao`.

**A RÉGUA NOVA** é `tests/unit/test_nenhuma_frase_de_aviso_chega_a_tela.py`. As
âncoras são lidas do dono quando ele existe (`CONFISSAO_ABERTURA`, `NAO_MEDI`,
`PREFIXO_DA_CURA` e as quatro `DICA_CANAL_*`); o aviso da mesa suja e a cor não
lida são trecho literal, porque o dono delas saiu. Ela lê a saída dos pacotes e
as vinte páginas (bancada e publicadas) sem o `.ajuda` nem os seletores
escondidos, prova o `?` do exame ainda com «O que fazer», e prova os três ramos
da 07 dublados (`test_os_tres_ramos_que_narravam_viram_rotulo_de_estado`, em
`tests/unit/test_o_cartao_da_steam_nao_narra.py`). A caminhada pelas dez abas no
WebKit ficou no driver do scratchpad, fora da suíte: a suíte não abre WebKit nem
fala com o daemon vivo.

**OITO ARQUIVOS DE TESTE FORA DA POSSE MUDARAM DE CONTRATO**, cada um com nota
datada — o contrato mudou, a régua não afrouxou:

* `tests/unit/test_a08_a_ordem_de_servico_e_a_sala_sao_da_maquina_dela.py` — o card traz o destino e não traz imperativo nem ganho; o `?` que fica é o da linha
* `tests/unit/test_a_aba_08_conexoes_fecha_as_linhas.py` — [03] e [04] viram «não volta»; o `+N` com destino
* `tests/unit/test_a_linha_fechada_da_aba08_segue_o_aparelho.py` — sem `confissao-dica`, na bancada e no pacote
* `tests/unit/test_a_fita_diz_o_controle_que_esta_na_mesa.py` — nome ou nada; o miolo do chip passa a ser lido do fim da etiqueta, não do `title=`
* `tests/unit/test_aba03_a_cor_ausente_no_mapa_nao_vira_borda.py` — a não lida diz o nome ou nada
* `tests/unit/test_o_cartao_diz_se_o_som_tem_para_onde_ir.py` — `TestADicaDoCanal` e o canal dormindo
* `tests/unit/test_a_aba_lancadores_diz_a_verdade.py` — pergunta a `DIZ_NAO_LI`
* `tests/unit/test_steam_input_d33_nomeia_o_jogo.py` — a mensagem 2 conta em vez de nomear

pytest nos 81 arquivos-alvo e nos oito acima: **1427 passed, 7 skipped, 0 failed**.
`ruff check` nos arquivos tocados: limpo.

**OS PORTÕES PEDIRAM MAIS QUATRO COISAS**, e duas são fora da posse:

* `a02_controles.regra_do_sono()` saiu: o `casa-sabe` a acusou sem chamador,
  porque a dica do canal parou de ler a regra.
* Um defeito meu, pego pelo `mypy`: o laço de `monta.fita` ganhou uma variável
  `titulo` que sombreava o parâmetro `titulo` da própria função. Renomeada.
* `tests/unit/test_portao_o_par_com_metade_ligada.py` (fora da posse): a citação
  de `a09_sistema.py` para a 08 passou a cair em linha em branco, e a 09 é
  `nao_toca:`. Ela entrou em `_CITACOES_PENDENTES` com o número certo medido
  pelo que o comentário promete, como o próprio portão manda.
* `docs/data/paridade-gtk-html.csv`, linha 299 (fora da posse): a linha dizia
  `IGUAL` para o aviso da mesa suja, com o sinal na sonda que saiu. Ela passou a
  descrever o que os dois lados fazem hoje — a dica do botão pedida ao mesmo
  dono, sem aviso — com nota datada no `porque`.

## Qual mordida prova

Cada mordida arrancou a cura sobre `6cd24565`, rodou a régua, devolveu por
`git checkout --` e rodou de novo. **`git diff` vazio depois de todas.**

| | cura arrancada | reprovou com a cura fora | com a cura de volta |
| --- | --- | --- | --- |
| M1 | a dica do botão volta a colar o aviso de outro programa | `test_a_dica_da_luz_nao_avisa_com_outro_programa_segurando_o_controle`, `test_a_dica_da_luz_nao_anexa_o_aviso_da_mesa_suja`, `TestSoAcionavelNoRadio::test_a_dica_do_radio_e_so_o_que_o_botao_faz` — 3 failed | 3 passed |
| M2 | a 08 volta a emitir `confissao-dica` | `test_a_linha_da_confissao_diz_a_conta_e_nao_confessa`, `test_a_confissao_conta_as_lacunas_da_bancada` — 2 failed | 2 passed |
| M3 | o imperativo volta ao card | `test_a_coluna_da_direita_da_08_nao_instrui_nem_confessa[Entrada 9]`, `test_a_coluna_nao_traz_cura_imperativo_nem_procedencia`, `test_a_ordem_de_servico_e_da_maquina_dela` — 3 failed | 4 passed |
| M3b | a linha do ganho (com `NAO_MEDI`) volta ao card | as mesmas três — 3 failed | 4 passed |
| M4 | a fita volta a dizer que a cor não foi lida | `test_a_cor_nao_lida_diz_o_nome_ou_nada`, `test_o_chip_sem_cor_diz_o_nome_ou_nada` — 2 failed | 2 passed |
| M5 | a dica do canal volta à frase do canal suspenso | `test_a_dica_do_canal_e_rotulo_de_estado`, `TestADicaDoCanal::test_a_dica_e_o_estado_lido_e_nada_mais[dormindo]` — 2 failed | 5 passed |
| M6 | o ramo de erro de leitura da Steam volta a narrar | `test_os_tres_ramos_que_narravam_viram_rotulo_de_estado` — 1 failed | 1 passed |
| M7 | o ramo ligado volta a nomear os jogos e o próximo ciclo | o mesmo e `test_conta_os_jogos_e_larga_a_palavra_conflito` — 2 failed | 2 passed |
| M8 | o gerador da 08 volta a cravar a dica de cor não lida, página regerada | `test_nenhuma_pagina_traz_aviso_fora_do_interrogacao[mockup/08-conexoes.html]` — 1 failed, 19 passed | 20 passed |

**UMA RÉGUA QUE NÃO MORDE, declarada:** em M5,
`TestOsSelosNoCartao::test_o_canal_dormindo_pinta_os_tres_campos` ficou verde,
porque compara o campo com a própria `dica_do_canal`. Ela mede a ligação, não a
frase; quem morde a frase são as duas acima.

**A MORDIDA NO PILOTO OCULTO:** M4 e M5 arrancadas juntas e as dez abas
passeadas de novo. Os achados foram de **3 para 15**: a frase de cor não lida
voltou na dica do chip das dez abas, e a do canal suspenso voltou na dica do
alto-falante da 02 — o `#hef-dica` mostrou a frase inteira no hover. Devolvidas:
diff vazio, e os perfis iguais por md5 (159 arquivos) depois de cada uma das três
corridas do piloto.

**ANTES E DEPOIS, as dez abas:** 24 achados → 3. Os três que ficam não são desta
sprint: a nota da 08 que cita o PipeWire ao descrever o áudio pelo cabo (descrição,
não aviso) e «O que fazer: nada.» duas vezes na 09 (SISTEMA-BOTOES-01).

**PORTÕES:** a corrida final roda com esta entrega no índice, e o resultado vai na
mensagem do commit. O vermelho que eu não posso curar é o `citacoes-de-linha`,
pela citação do mapa de canais — ver o primeiro item de «O que sobrou».

## O que NÃO verifiquei

* **Os três ramos da 07 na tela viva.** A máquina dela não está em nenhum (Steam
  achada, biblioteca lida, Steam Input desligado): as fotos da 07 antes e depois
  são iguais. Só o unitário com os ramos dublados.
* **A coluna da ordem com destino na tela viva.** As duas ordens dela não têm
  destino; o de→para só foi medido no unitário.
* **A dica da luz com o mouse sobre o botão aberto.** O botão mora na seção
  «Gestão de Controles», fechada; o piloto disparou o hover em (0,0) e leu o
  `#hef-dica`. As seções fechadas da 06 e da 08 não foram abertas (§R da sprint).
* **O dublê do controle segurado no piloto depois da cura.** A sonda saiu, então o
  dublê do driver não tem mais onde prender. O estado segurado foi dublado no
  unitário, uma camada abaixo (`sinal_da_barra.limpo_para_conectar`). A razão
  «▲ nasceu com 1 processo(s)…» que apareceu no piloto é leitura do daemon vivo.
* **Aparelho, cabo e rádio:** nada tocado. A janela instalada dela: nada instalado.
* **A suíte inteira:** não rodada; só os arquivos-alvo e os que mudaram de contrato.
* **O Steam Input com exceção por jogo:** não medido.

## O que sobrou para o próximo

* **A CITAÇÃO DO MAPA DE CANAIS, e é de quem coordena.** A linha 23 de
  `docs/data/mapa-controles.csv` (`audio.microfone@dualsense`, `radio_detalhe`)
  cita a linha 4119 de `a02_controles.py` para `mic_modo`. A 02 encolheu nesta
  sprint, e `mic_modo` está hoje na linha 4102 — medido por `grep -n`. O
  preâmbulo do lote diz que eu não edito esse CSV fora da posse; eu o cito e
  relato. Trocar 4119 por 4102 fecha o `citacoes-de-linha`.
* **08, dica da luz:** a razão «▲ nasceu com 1 processo(s) segurando o nó do
  controle — nesta condição a barra não obedece, e só a reconexão devolve»
  continua. É estado com consequência, lido do nascimento; fica para o VALIDA
  julgar se é aviso.
* **08, a coluna da direita fica vazia** quando as ordens não têm destino, que é o
  caso da máquina dela: espaço em branco ao lado de «2 mudanças recomendadas». É o
  custo que a §R declarou; o olho dela decide.
* **07:** o sufixo «· Exceção por jogo: N jogo(s) — …» ainda passa de seis
  palavras quando há exceção; `STEAM_NAO_ENCONTRADA` (o ramo sem leitura) ainda
  narra; o corpo «Os controles chegam. O atalho…» é longo, mas é a decisão 07[04].
  O detalhe do erro de leitura saiu da tela.
* **`a07_lancadores`** ainda traduz os nomes dos jogos para a linha do Steam Input,
  que agora só conta — leitura de disco sem uso. O arquivo é `nao_toca` desta
  sprint.
* **Sobras de nome:** o cache `_REGRA_DO_SONO` da 02 segue escrito a cada
  leitura, e só a régua do som o lê;
  `scripts/ensaios/a_linha_fechada_da_08_no_webkit.py` ainda lê `confissao-dica`
  e vai devolver nulo; a docstring de
  `tests/unit/test_a_cor_dela_vence_e_nao_vaza_para_o_vizinho.py` cita
  `_perguntar_pela_mesa`, que saiu; `aba08.BORDA_NEUTRA` segue sem uso, como já
  estava.
* **09:** a cor não lida e «O que fazer: nada.» da aba Sistema são da
  SISTEMA-BOTOES-01.
