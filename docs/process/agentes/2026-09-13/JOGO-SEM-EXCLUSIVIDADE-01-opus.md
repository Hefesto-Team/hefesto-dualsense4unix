# JOGO-SEM-EXCLUSIVIDADE-01 — nenhum jogo foge do modo e da máscara da aba Jogar

**Árvore:** `hefesto-voo/JOGO-SEM-EXCLUSIVIDADE-01-opus` · branch
`voo/JOGO-SEM-EXCLUSIVIDADE-01-opus` · base `249af1f6` (= `onda/1309`) ·
**aparelho: não usei** (`bancada: false`). A sprint não traz nota «ROTA
CORRIGIDA»; valeram §D, §I e §V. Tudo o que escreve foi medido em lar de
mentira. O disco dela foi só LIDO: o `localconfig.vdf`, os backups ao lado dele,
a árvore `Steam Controller Configs`, o `console_log` da Steam e o journal do
vigia. O md5 do `localconfig.vdf` e o da listagem da árvore de configs saíram
idênticos antes e depois da simulação. O vigia instalado não foi tocado, o
piloto não foi aberto e nenhum perfil dela foi lido ou escrito.

**O ACHADO QUE A COSTURA PRECISA LER ANTES DO PASSO 2.** O estudo mediu que os
jogos da queixa não tinham `UseSteamControllerConfig`. Eles têm — em `"0"`, na
árvore viva `UserLocalConfigStore/apps`, que é onde a ponte escreve. As duas
árvores `apps` de cima não guardam a chave nenhuma, e foi nelas que a leitura
anterior olhou. Três leituras, nenhuma escrita:

1. **A simulação** `steam_input_ponte.py --desligar-fora-da-lista --dry-run`
   contra o disco dela devolveu `ja_desligado` para 1599660, 3357650, 2111190 e
   2497900 — os quatro da queixa —, e também para 1245620, 316790 e 413080. Ela
   gravaria `"0"` em quatro jogos que ela não citou: 1672970, 1828690, 2958790 e
   3449040. O 413090 saiu `jogo_desconhecido_neste_vdf`.
2. **A linha do tempo dos backups** `.bak.*` do vdf: o valor desses quatro na
   árvore viva é `"0"` em todos os backups de 11/09 06:44 a 13/09 05:30,
   inclusive o de 13/09 01:16. Em 19/08 18:48 eram `"2"` (Sackboy, Mullet Mad
   Jack e Pragmata), e o vigia os desceu desde então.
3. **O `console_log` da Steam**, 13/09: o avaliador `reaper SteamLaunch
   AppId=1599660 Install=1 -- …` roda às 01:29:30. Às 01:29:43 aparecem
   `Loaded Config for Local Selection Path for App ID 1599660` (um layout da
   oficina) e `Created virtual controller at slot 0`. A mesma dupla volta às
   01:30:56. **O `"0"` já estava lá e a Steam criou o controle virtual mesmo
   assim.**

Então o passo 2, como a §I o escreve, **não muda o disco dos quatro jogos da
queixa**, e a hipótese de que o `"0"` vence a configuração por jogo perdeu o
disco a seu favor. Quem fecha é o aparelho (MESA-DE-QUATRO-01). O passo 1 não
depende disto e fica de pé sozinho.

## O que mudou

### 1. O install script deixou de ser jogo vivo — `integrations/steam_launch_options.py`

* `e_avaliador_do_install_script(cmd)` diz se a cmdline é o avaliador. Ela
  procura o token `Install=1` só entre os argumentos do `reaper` (depois de
  `SteamLaunch AppId=<dígitos>` e antes do `--`), então argumento do jogo não
  conta. É por assinatura: nenhum appid no produto. A forma bate com as oito
  linhas do `console_log` de 13/09, seis de 1599660 e duas de 2424420.
* `steam_game_running_appid()`, a evidência E4 do sinal de jogo, devolve `None`
  para o avaliador. `steam_game_running()`, que guarda o `steam -shutdown`
  (DEDUP-05), continua respondendo `True`.
* `_steam_launch_cmdline`, as duas camadas que podiam esconder o jogo atrás do
  avaliador:
  * **camada 4**: a varredura prefere o jogo ao avaliador, qualquer que seja a
    ordem dos pids. O avaliador sozinho continua sendo a resposta.
  * **camada 2**: com o avaliador na foto, a varredura roda de novo em vez de
    reconfirmar só ele. Sem isso, o jogo fora do wrapper que nasce ao lado dele
    ficaria invisível enquanto o avaliador vivesse.
* O comentário da agulha dizia que `running()` e `appid()` eram «consistentes
  por construção». Agora ele nomeia a única discordância desenhada, que é o
  avaliador.
* `daemon/subsystems/game_signal.py`: só a docstring de `classify`. O fato
  «`SteamLaunch AppId=` só existe no launch de um jogo» foi substituído, com
  NOTA DATADA.
* `scripts/disable_steam_input.sh`: o comentário do `pgrep` afirmava o mesmo
  fato e foi corrigido lá também. Ali contar o avaliador é o certo.

### 2. O outro sentido da lista — `integrations/steam_input_ponte.py`

* **Puras:**
  * `appids_com_autosave(texto)` lê um `configset_*.vdf`. Só `autosave` de
    appid numérico conta; `template`, `workshop` e chave como `<appid>-testing`
    ficam de fora. Forma que não se entende devolve `None`.
  * `desligar_no_texto` é o espelho de `ligar_no_texto`: os dois passaram a
    dividir `_garantir_no_texto`, com as mesmas duas réguas e a mesma recusa de
    inventar bloco.
  * `conferir_escrita` ganhou `valor=`.
* **Leitura:**
  * `pasta_das_configs_por_jogo(vdf)` leva
    `userdata/<conta>/config/localconfig.vdf` para
    `steamapps/common/Steam Controller Configs/<conta>/config`. Conferido no
    disco dela: a conta da árvore de configs é a mesma do `userdata` que tem
    `localconfig.vdf`.
  * `configuracao_por_jogo(pasta)` conta o appid com `autosave` em algum
    configset OU com pasta `<appid>/`. Qualquer configset ilegível devolve
    `None` para a conta inteira. O nome do arquivo não sai da função, porque
    pode carregar o id de um aparelho.
  * `_ler_allowlist_estrita`: lista que existe e não se deixa ler devolve
    `None`. Lida vazia por engano, ela desligaria os jogos que ela pôs lá.
* **`garantir_fora_da_lista_desligado`:** os mesmos portões e a mesma escrita
  da ponte. Nada a fazer vem antes de jogo aberto, que vem antes de Steam
  aberta. O backup é `.bak.steam-input-fora-da-lista-<ts>`, a escrita é
  `tmp` + `replace` e a segunda régua confere antes de trocar o arquivo.
* **CLI `--desligar-fora-da-lista`**, no mesmo grupo exclusivo de `--ligar` e
  `--estado`. A saída é `[steam-input-fora-da-lista] resultado=<status>`. O
  `_RESULTADO_RE` da janela casa só `^\[steam-input\] resultado=`, e a última
  linha do vigia continua sendo a dele.

### 3. O vigia — `scripts/disable_steam_input.sh`

`ligar_ponte_da_allowlist` chama `--desligar-fora-da-lista` logo depois do
`--ligar`, com a mesma guarda de Steam viva e o mesmo `|| true`. Os dois modos
que já chamavam a função, `--apply` e `--apply-quiet`, ganham a bandeira nova
sem mudança de pré-voo.

### 4. Os testes novos

* `tests/unit/test_o_install_script_nao_e_jogo_vivo.py` tem 9 casos:
  * as duas perguntas separadas, com os dois appids do log;
  * o token só nos argumentos do `reaper`;
  * o jogo de verdade continua sendo jogo;
  * o avaliador não esconde o jogo, nas duas ordens de pid e através da foto;
  * o fio inteiro: `steam_game_running_appid` → `classify` → `GameSignal` →
    `arm_launch_profile` → `ponte_tentativa.comecar`, que dá `primeiro_degrau`;
  * a contraprova com o jogo vivo, que dá `jogo_vivo`.
* `tests/unit/test_o_steam_input_por_jogo_segue_a_lista.py` tem 27 casos:
  * o parser e oito formas malformadas;
  * a pasta do jogo;
  * o endereço da conta;
  * os três casos do `"0"` no texto;
  * o lar de mentira: três configurados fora da lista vão a `"0"`, o da lista
    fica em `"2"`, o sem configuração fica sem chave. O vdf é relido pelo parser
    antes e depois, o perfil de jogo de mentira sai byte a byte idêntico, e a
    fotografia md5 do lar inteiro só muda no vdf e nos backups dele;
  * a segunda rodada não escreve;
  * configset ilegível, lista ilegível, sem lista, Steam aberta e jogo aberto;
  * o vigia em bash de verdade. Nem `configset_` nem o rótulo do configset
    «de aparelho» aparecem na saída.

```
tests/unit/test_o_install_script_nao_e_jogo_vivo.py tests/unit/test_o_steam_input_por_jogo_segue_a_lista.py
36 passed in 0.87s
```

### 5. As réguas vizinhas

As três da posse (`test_ponte_steam_input_01_a_lista_que_so_preservava.py`,
`test_o_vigia_do_steam_input_nao_nasce_morto.py`,
`test_r06_allowlist_steam_input.py`) continuam verdes, sem mudar de contrato.
Rodaram junto com `test_steam_launch_scan.py`,
`test_ponte_escada_laco_01_quem_sobe_a_escada.py`,
`test_steam_input_honestidade.py`, `test_steam_input_ponteiros.py`,
`test_t15_a_allowlist_tem_um_caminho_so.py`,
`test_a_porta_que_a_casa_construiu_01.py`,
`test_t03_o_conselho_que_serve_para_esta_instalacao.py`,
`test_bg05_a_lista_de_bases_e_uma_so.py`, `test_steam_launch_options_vdf.py` e
`test_daemon_acordado_01_bg03_o_pgrep_que_a_janela_forka.py`:

```
303 passed, 1 skipped in 6.77s
```

`ruff` limpo nos arquivos mexidos, `mypy` limpo nos dois módulos e `bash -n`
limpo. O `shellcheck` só aponta três avisos que já existiam em linhas que não
toquei.

**Tela:** nada visível mudou, e por isso não há foto. `steam_game_running_appid`
alimenta a aba «No jogo» e o «Detectar o jogo que está aberto»: durante os
segundos do avaliador, os dois deixam de ver jogo.

**Mapa:** nenhuma célula de `docs/data/mapa-controles.csv` cobre a agulha de
jogo vivo nem o Steam Input por jogo (busca por Steam Input, autoridade e
install na coluna de chave: zero).

## Qual mordida prova

Cada cura foi arrancada por script, a régua rodou e o arquivo foi devolvido com
o md5 conferido (7 de 7 devolvidos). O `git diff --stat` final só tem as
mudanças desta entrega.

| cura arrancada | régua | com a cura arrancada |
| --- | --- | --- |
| a exclusão em `steam_game_running_appid` | o arquivo do install script | 4 failed, 5 passed |
| a preferência da camada 4 | `-k nao_esconde_o_jogo_que_convive` | 1 failed (avaliador com pid menor), 1 passed |
| a nova varredura da camada 2 | `-k foto_do_avaliador` | 1 failed |
| o `"0"` (`desligar_no_texto` trocado por nada) | `-k "TestOLarDeMentira or o_vigia"` | 5 failed, 3 passed |
| a lista lida como vazia | idem | 3 failed, 5 passed — o jogo da lista cai para `"0"` |
| a falha fechada do configset (`None` vira `continue`) | `-k ilegivel` | 1 failed, 1 passed |
| a chamada `--desligar-fora-da-lista` no vigia | `-k o_vigia` | 1 failed |

A primeira é a do §V: sem a exclusão, o fio reproduz a linha do journal das
05:00:20.

```
E       AssertionError: o lançamento caiu em ['jogo_vivo'] com a autoridade em 'game'
E       assert ['jogo_vivo'] == ['primeiro_degrau']
[info     ] ponte_escada_nao_arma          appid=1599660 degrau=gamepad/dualsense motivo=jogo_vivo preco=so_com_gesto
[info     ] launch_arm_perfil_sem_modo     appid=1599660 escada=jogo_vivo profile=jogo-com-install-script
FAILED tests/unit/test_o_install_script_nao_e_jogo_vivo.py::test_com_o_avaliador_vivo_o_lancamento_arma_o_primeiro_degrau
```

Com a cura devolvida, o `cmp` contra a cópia de antes da mordida sai idêntico, e
os dois arquivos dão `36 passed`.

## O que NÃO verifiquei

* **O aparelho, nada.** A bancada não foi chamada. Fica para a
  MESA-DE-QUATRO-01:
  * se o `"0"` vence a configuração por jogo — e o disco já diz que não venceu
    às 01:29 e às 01:30;
  * se o Sackboy passa a mostrar a máscara da Jogar;
  * se a escada arma o primeiro degrau e confirma por silêncio numa abertura
    real;
  * se o DON'T SCREAM e o Mullet Mad Jack perdem controle. Na máquina dela os
    dois já estão em `"0"`, então o passo 2 não muda o risco deles.
* **A cmdline VIVA do avaliador em `/proc`.** O teste usa a forma do
  `console_log`, e o `/proc` separa os argumentos por NUL, que a varredura
  troca por espaço. Não peguei um avaliador vivo para ler.
* **O Pragmata e o Mullet Mad Jack vivos.** Não há abertura deles nos logs
  retidos.
* **`template` e `workshop` sem pasta própria** (2358720 no disco dela) não
  contam, por leitura literal da §I.2, que fala em `autosave`. Não medi se a
  Steam liga o Steam Input por eles.
* **O teste do vigia em bash roda o `steam_game_running()` real** (varre o
  `/proc` desta máquina), igual ao teste irmão da ponte. Com um jogo dela
  aberto ele adia e reprova. Nas corridas desta sprint não havia jogo.
* **O `--status` e o pré-voo do `--apply` do vigia não enxergam a pendência
  nova.** Não mexi, para não mudar o `resultado=` que a aba Sistema lê. O doctor
  e o prontuário continuam cegos à configuração por jogo, e estão fora da posse.
* Não rodei a suíte inteira (regra da leva). Os portões estão no fim desta
  leva.

## O que sobrou para o próximo

1. **Para quem coordena, antes de costurar o passo 2:** o achado do topo. O
   próximo lugar a medir é a própria configuração por jogo da Steam — a entrada
   `autosave` do configset, a pasta `config/<appid>/` e o layout da oficina que
   o `console_log` mostra carregando. Neutralizá-la mexe em configuração da
   Steam que não é do Hefesto. A decisão é de quem coordena, com a
   MESA-DE-QUATRO-01 medindo antes. O passo 1 é independente, e os arquivos
   dele são `steam_launch_options.py`, a docstring de `game_signal.py` e
   `tests/unit/test_o_install_script_nao_e_jogo_vivo.py`.
2. **O aviso do §R precisa de uma troca de nomes.** Na próxima saída da Steam, o
   vigia costurado grava `"0"` em 1672970, 1828690, 2958790 e 3449040. O DON'T
   SCREAM e o Mullet Mad Jack não mudam: já estão em `"0"`.
3. `tests/unit/test_steam_launch_scan.py` chama de «invariante de construção»
   (`test_running_e_appid_nunca_discordam`) o que agora tem uma exceção
   desenhada: o avaliador. O teste passa porque os mapas dele não têm
   avaliador. Fora da posse.
4. `docs/process/agentes/2026-08-26/LEVA-3-A.md` repete «só existe no launch de
   um jogo». É entrega histórica e está fora da posse.
5. `storm_doctor`, `prontuario_dos_jogos` e o `--status` do vigia seguem lendo
   só `UseSteamControllerConfig`.
6. A corrida da evidência E3 do §R continua aberta.
