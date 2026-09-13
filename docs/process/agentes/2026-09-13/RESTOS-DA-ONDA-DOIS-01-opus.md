# RESTOS-DA-ONDA-DOIS-01 — o alto-falante sem endereço, o touchpad na troca, a varredura sem leitor e o número do Parar (IMPLEMENTA, opus)

Sprint: [RESTOS-DA-ONDA-DOIS-01](../../sprints/2026-09-13-RESTOS-DA-ONDA-DOIS-01-o-alto-falante-sem-endereco-o-touchpad-na-troca-a-varredura-sem-leitor-e-o-numero-do-parar.md)
· lote `1309-onda3` · branch `voo/RESTOS-DA-ONDA-DOIS-01-opus` · base `b791d234`
(conferida igual a `onda/1309`) · `bancada: false`: nenhum aparelho, nenhum
`systemctl`, nenhum gesto ao daemon dela. Valeram as seções §D, §I e §V.

O python é o da venv da árvore principal, com o `PYTHONPATH` desta árvore
(esta árvore não tem `.venv`); o import foi conferido em `…-opus/src`.

## O que mudou

| §I | onde | o que mudou |
| --- | --- | --- |
| 1 | `interface/aba02.py` | A moldura do alto-falante troca `data-campo="som-sem-endereco" … data-hef-atributo="title"` por `data-campo="alto-apagado" … data-hef-atributo="data-apagado"`. As cinco regras da folha passam de `[title]` a `[data-apagado="sem-alvo"]`. Os dois comentários da guarda dizem por quê, com a mesma contagem de linhas. |
| 1 | `interface/pacotes/a02_controles.py` | O campo do cartão passa de `som-sem-endereco` (valor: a frase `TEXTO_AUDIO_SEM_ENDERECO`) a `alto-apagado` (valor: `MIC_SEM_ALVO`, o mesmo `sem-alvo` do microfone). O import da frase saiu. A docstring de `microfone_apagado` e o comentário das duas constantes deixaram de citar o campo morto. O arquivo manteve as 4412 linhas, porque as planilhas `nao_toca:` o citam por número. |
| 2 | `interface/aba06.py` | `TELA_REMAPEAMENTO` desenha a primeira coluna com `b.removesuffix(MARCA_DO_TOUCHPAD)`: as três linhas do touchpad da troca saem sem a marca, e `BOTOES` (as Definições e as outras telas) fica igual. A autoconferência do gerador ganha o passo 4-ter-bis: nenhuma marca na troca, e três nas Definições. Dois comentários de 11/09 que contavam «nove» lugares passaram ao passado. As 11 linhas novas ficam depois de toda citação por número deste arquivo. |
| 3 | `app/actions/emulation_actions.py` | Medido quem lê o `efetiva`: nada vivo. `markup_status_steam_input` o ignorava desde a FRASES-E-DICAS-03, e o outro chamador, `_refresh_steam_input_status`, é da janela GTK. Nenhuma classe do `src/` herda `EmulationActionsMixin` (`git grep` de `class …ActionsMixin`), e o `app/app.py` que a montava saiu em 06/09 (`D-0609-GTK-LEVA-INTEIRA`, na docstring de `app/__init__.py`). Então `markup_status_steam_input(on, jogos, excecoes)` perdeu o parâmetro, e `_steam_input_excecao_status` virou `_steam_input_excecoes()`: devolve só a lista e não varre hidraw. A docstring guarda a distinção do R-06 com nota datada e aponta quem continua medindo o físico exposto (`physical_nodes_exposure`, que o `doctor.sh` chama). O arquivo manteve as 2253 linhas, porque a 09 e a planilha de paridade citam `on_camadas_engasgo` por número. |
| 3 | `interface/pacotes/a07_lancadores.py` | `_o_que_a_steam_poe_no_meio` chama `_steam_input_excecoes()` e passa três valores. |
| 4 | `interface/aba09.py` | O `title` do Parar: «O Hefesto deixa de rodar e os controles viram gamepads comuns do Linux. Pergunta antes, dizendo o que se perde.» O `N` continua servindo às outras frases da aba. |
| — | `mockup/` e `interface/paginas/` 02, 06 e 09 | Regeradas pelos geradores e publicadas com `check_o_desenho_aprovado.py --publicar 02 06 09` («3 mudou/mudaram de fato»). O `mockup/` e o publicado saíram iguais byte a byte. |
| 5 | **nova** `tests/unit/test_os_restos_da_onda_dois.py` | 13 casos. A 02 abre o piloto do produto oculto com a mesa dublê de três (P2 com `uniq` vazio) e mede a moldura do alto-falante de cada cartão: atributo, opacidade EFETIVA e cursor. Mede também a frase fora da tela e a folha sem `[title]` (bancada e publicado). A 06: a marca sai da troca e fica nas Definições (bancada e publicado). A 07: a leitura do Steam Input com `physical_nodes_exposure` e `os.listdir` vigiados, e a assinatura sem o `efetiva`. A 09: o `title` do Parar sem dígito (bancada e publicado), e a pergunta do clique 1 sem dígito. |

**As réguas que passavam o valor, com nota datada** (a ordem do §I 3). Cinco
estão fora da `posse:`, e todas reprovariam a cura:

* na posse: `test_o_cartao_diz_se_o_som_tem_para_onde_ir.py` (o `DA_BANCADA`, as seções 3, 6 e 8 e a docstring passam ao `alto-apagado`; o cartão sem endereço não carrega mais a frase) e `test_steam_input_d33_nomeia_o_jogo.py` (a chamada sem `efetiva`);
* fora da posse: `test_r06_status_honesto.py` (os três estados do físico agora cobram a mesma contagem e nenhuma varredura; `TestExposicaoDoFisico` fica intacta), `test_a_aba_07_lancadores_fecha_as_linhas.py` e `test_o_cartao_da_steam_nao_narra.py` (dublam `_steam_input_excecoes`), `test_nenhuma_frase_de_aviso_chega_a_tela.py` (um estado só, e a linha termina na contagem) e `test_ambiente_presumido_01_a_steam_dos_quatro_layouts.py` (três argumentos);
* fora da posse, pela 06: `test_a_aba_06_navegacao_fecha_as_linhas.py`. As duas réguas da marca passam a ler o documento sem a tela da troca (`_sem_a_troca`), com a razão na docstring.

**E o portão `casa-sabe`, fora da posse.** A primeira corrida dos portões
reprovou 2 de 60. O `acentuacao` pegou uma chave `pagina` na régua nova, que
virou `abertura`. O `casa-sabe` acusou `broker/hidraw_broker.py::physical_nodes_exposure`
sem chamador em produção: o único era a varredura que a 07 deixou de fazer. O
que sobra chamando é o `_censo_de_fisicos` do `scripts/doctor.sh`, que é
diagnóstico e que o portão não conta. A função foi declarada em
`_NAO_E_PROMESSA` de `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`,
com a data, a evidência e as duas réguas que a exercitam.

**Nenhum botão novo.** Nas páginas publicadas e no `mockup/`, antes e depois:

| página | `<button` | `data-gesto` | `title=` | `<input` | `<select` | `data-campo` |
| --- | --- | --- | --- | --- | --- | --- |
| 02 | 43 → 43 | 55 → 55 | 72 → 72 | 15 → 15 | 2 → 2 | 525 → 525 |
| 06 | 12 → 12 | 89 → 89 | 46 → **43** | 13 → 13 | 63 → 63 | 95 → 95 |
| 09 | 18 → 18 | 15 → 15 | 37 → 37 | 0 → 0 | 7 → 7 | 37 → 37 |

Os três `title` a menos na 06 são as três marcas da troca.

### A tela, no piloto oculto

Roteiros no rascunho, fora do git (`comum.py`, `driver_02.py`, `driver_06.py`,
`driver_09.py`). Eles montam um lar de mentira (`HOME`, `XDG_*` e
`XDG_RUNTIME_DIR` desviados, sem alcançar o socket do daemon dela nem o som),
ligam `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, usam o Xvfb da guarda e
dublam `mesa_viva.estado_do_daemon`. O ANTES rodou sobre a árvore intocada,
antes da primeira edição. Os perfis dela (159 arquivos) foram copiados antes e
saíram iguais por md5 depois das duas levas de corrida.

**02, com o P2 sem endereço aberto** (P1 no cabo e P3 no rádio, com endereço):

| cartão P2 | ANTES | DEPOIS |
| --- | --- | --- |
| `data-apagado` da moldura do alto-falante | ausente | `sem-alvo` |
| `data-hef-dica` da moldura | «Som desligado: este controle está sem endereço» | ausente |
| linha do volume e fileira da rota (opacidade efetiva) | 1 e 1 | 0,45 e 0,45 |
| cursor do deslizante e dos botões da rota | `pointer` | `not-allowed` |
| a frase em texto visível, `title` ou dica, na página inteira | 1 dica | 0 |
| P1 e P3 (alto-falante) | acesos | acesos |
| `button` e `data-gesto` no DOM | 40 e 48 | 40 e 48 |

O ANTES é o defeito do §E, e um pouco pior que a descrição. A guarda não
acendia, e a frase de aviso chegava à tela como dica flutuante sobre um bloco
aceso. Fotos: `RESTOS-DA-ONDA-DOIS-01-ANTES-02-alto-falante-sem-endereco.png` e
`…-DEPOIS-02-…`, nesta pasta.

**06, a tela «Trocar os botões» aberta pelo link real, e as Definições:** ANTES,
as três linhas do touchpad da troca com a marca e a lista apagada, e 11 marcas
no documento. DEPOIS, as três sem a marca (a lista continua apagada), as três
das Definições com a marca e 8 marcas no documento. Em `button` e `data-gesto`
o DOM tem 12 e 86 nos dois. Fotos: `…-ANTES-06-trocar-os-botoes.png` e
`…-DEPOIS-06-…`.

**09, o clique no Parar.** O `systemctl` é o da janela de mentira da régua da
SISTEMA-BOTOES-01. `ativar_o_servico` é um espião, e a mesa dublê tem UM
controle. Um clique só; o segundo nunca foi dado.

| | ANTES | DEPOIS |
| --- | --- | --- |
| painel depois do clique 1 | «O Hefesto deixa de rodar e os 2 viram gamepads comuns do Linux. …» e «Clique de novo para confirmar.» | «… e os controles viram gamepads comuns do Linux. …» e «Clique de novo para confirmar.» |
| rótulo do botão | «Confirma?» | «Confirma?» |
| `systemctl` anotado · ativações | nenhum · 0 | nenhum · 0 |
| desfecho do gesto | `aplicou` | `aplicou` |

Fotos: `…-ANTES-09-a-pergunta-do-parar.png` e `…-DEPOIS-09-…`.

## Qual mordida prova

Roteiro `mordidas.py`, no rascunho. Cada mordida guarda os bytes e o sha256 do
`git diff` e sabota, conferindo a contagem do trecho trocado. Quando mexe em
gerador, regera e publica. Roda a régua nova com o cache de bytecode num
prefixo vazio, devolve os bytes, regera e publica de novo, e confere o
`git diff`.

| | cura arrancada | com a cura fora | de volta |
| --- | --- | --- | --- |
| M1 | as cinco regras do alto-falante de volta a `[title]`, com a 02 regerada e publicada | **3 failed**: `test_a_02_o_alto_falante_sem_endereco_apaga_no_webkit` e `test_a_02_a_moldura_do_alto_falante_tem_endereco_proprio[bancada/publicado]` | 6 passed, `git diff` idêntico |
| M2a | a marca de volta à troca, só no gerador | o gerador para: «a tela da troca voltou a marcar o touchpad com «não dispara» …», rc=1 | gera e publica com rc=0, `git diff` idêntico |
| M2b | a marca de volta, a autoconferência calada, a 06 regerada e publicada | **2 failed**: `test_a_06_a_marca_sai_da_troca_e_fica_nas_definicoes[bancada/publicado]` | 2 passed, `git diff` idêntico |
| M3 | `a07_lancadores.py` e `emulation_actions.py` da base (a varredura e o `efetiva`) | **2 failed**: `test_a_07_a_leitura_do_steam_input_nao_varre_hidraw` e `test_a_07_a_assinatura_do_status_nao_pede_o_efetiva` | 2 passed, `git diff` idêntico |
| M4 | o `{N}` de volta ao `title` do Parar, com a 09 regerada e publicada | **3 failed**: `test_a_09_o_title_do_parar_nao_crava_numero[bancada/publicado]` e `test_a_09_a_pergunta_do_parar_nao_crava_numero` | 3 passed, `git diff` idêntico |

**A M1 NA TELA** é o próprio ANTES do piloto: com a folha em `[title]`, a
moldura do P2 fica acesa e a frase vai para o `data-hef-dica`.

**Réguas pontuais, na árvore curada:**

* a nova e as da posse, mais as cinco de fora da posse e a das seis linhas da troca: 209 passed;
* a nova em modo detalhado (o `setup` do WebKit levou 3,43 s, e nada pulou), junto com a da 07: 43 passed;
* `scripts/validar-citacoes-de-linha.py --all`: OK, 3288 citações;
* `tests/unit/test_portao_o_par_com_metade_ligada.py`: 16 passed;
* `ruff check` nos 14 arquivos tocados: `All checks passed!` (os avisos de `# noqa` inválido já existiam em `aba02.py` e `a02_controles.py`);
* `mypy` em `emulation_actions.py`, `a07_lancadores.py` e `a02_controles.py`: `Success: no issues found in 3 source files`.

**Réguas vizinhas:** os 147 arquivos de `tests/unit` que citam as três páginas,
os geradores, os pacotes 02, 07 e 09, `markup_status_steam_input`, a marca ou o
`data-bloco`, em três partes:

* A: 904 passed e 1 failed;
* B: 932 passed e 4 xfailed;
* C: 715 passed e 9 skipped.

O vermelho da parte A é
`test_a02_os_botoes_do_som_fazem_o_que_dizem.py::TestOQueATelaAcende::test_com_mix_a_fileira_acende_o_ouvir_junto`
(`aceso_da_fileira(… fonte="sfx")` devolveu `""`), e ele é intermitente:

* em seis corridas seguidas da mesma parte A nesta árvore, a régua passou nas seis (905 passed cada);
* isolado, passou três vezes aqui e três vezes na base extraída por `git archive` no rascunho (19 passed cada), alternando;
* o diff desta sprint não toca `aceso_da_fileira`, `_camada_1` nem `_SONO` (0 ocorrências);
* a parte A inteira não roda na base extraída, porque falta `assets/`.

## O que NÃO verifiquei

* **O aparelho e o daemon vivo.** O controle sem endereço é dublê, com `uniq`
  vazio. Não remedi se o daemon de hoje publica algum controle assim, nem em qual
  das três formas que `uniq_do_entry` aceita (`None`, vazio, brancos).
* **O ponteiro sobre a moldura apagada.** Não passei o mouse. Medi o
  `data-hef-dica` da moldura ausente e a frase ausente de toda dica da página.
* **O clique nas peças apagadas do alto-falante no WebKitGTK.** Medi cursor e
  opacidade; nenhum deslizante nem botão da rota foi clicado.
* **O clique 2 do Parar**, por regra. E nenhum Parar, Ativar ou Reiniciar de verdade.
* **Uma exceção de Steam Input de verdade.** A lista foi dublada nas réguas; a
  07 não foi pilotada na tela, porque a linha visível não mudou (a contagem já
  era a mesma).
* **O refresh GTK da aba Emulação numa janela.** Só pela régua do R-06, com o
  mixin montado à mão.
* **A navegação pelo controle e o leitor de tela** sobre a tela da troca sem a marca.
* **A suíte inteira**, por ordem do despacho.
* **Os portões depois desta última frase.** A corrida completa, com tudo no
  índice, deu «TODOS VERDES — 60 portões»; esta linha foi a única coisa escrita
  depois dela.

## O que sobrou para o próximo

1. **Quem costura regera as dez:** 02, 06 e 09 mudaram pelos geradores.
2. **`docs/data/paridade-gtk-html.csv`, linha 57** (`nao_toca:`). A prosa diz que
   a guarda nasceu «pelo endereço `som-sem-endereco`» e cita números antigos da
   02, e o `html_faz` descreve «os dois `?` dizem a razão». Hoje o endereço é
   `alto-apagado` (moldura do alto-falante) e `mic-apagado` (moldura do
   microfone). É da CITACOES-DAS-PLANILHAS-01 ou de quem for dono da paridade.
3. **Outro cinza por `[title]` na casa:** `.degradou[title]` na 01 e na 02 (a
   marca da emulação degradada). A camada da dica da casa tira o `title` do DOM
   vivo, e é a mesma forma do defeito que esta sprint curou; a marca pode nunca
   aparecer no WebKit. Não medi no DOM.
4. **A janela GTK da aba Emulação é código sem leitor.** Nenhuma classe do
   `src/` herda `EmulationActionsMixin`, e `_refresh_steam_input_status` só é
   exercido pela régua do R-06. Tirá-lo é de quem cuidar do resto da GTK.
5. **O vermelho intermitente** `test_com_mix_a_fileira_acende_o_ouvir_junto`
   (medido acima). Merece as três voltas do lote isolado numa árvore com `assets/`.
6. **Registro datado que ainda diz «os 2»:**
   `docs/process/2026-09-03-CLIQUE-A-ABA-09.md` cita o `title` do Parar como ele
   era em 03/09. Não mexi: é a medição daquele dia.
7. **Para a SPECS-A-PROCEDENCIA-01**, pela chave `audio.alto_falante`: a guarda
   sem endereço do cartão foi vista apagando no WebKit, com a mesa dublê (P2 no
   rádio). Degrau MONTOU, sem aparelho.
8. **A docstring de `physical_nodes_exposure`** (`broker/hidraw_broker.py`, fora
   da posse) ainda diz que «a GUI e o `doctor.sh` passam a consultar». Desde
   esta sprint só o `doctor.sh` consulta. Não mexi porque o arquivo é o que o
   instalador copia para fora do checkout; a declaração no `casa-sabe` já diz
   que a frase caducou.
