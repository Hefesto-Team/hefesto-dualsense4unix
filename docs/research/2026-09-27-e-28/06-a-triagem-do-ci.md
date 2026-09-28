# A triagem do CI vermelho do dev

Os vermelhos que sobraram no CI do `dev` em 27/09/2026, reproduzidos num clone limpo e curados na origem: a causa de cada um, a cura, a mordida e o que ficou aberto.

## O ponto de partida

A corrida 36354426805 do CI (commit `e4f06a523`) mediu o `dev` com duas
mudanças novas:

- o job **lint-test** roda sem PyGObject, e o teste que cai pela falta do GTK
  **pula** com o motivo (a regra é `pytest_runtest_makereport` com
  `_falta_o_gtk`, em `tests/conftest.py:435` e `:455`);
- o job **gtk-real** roda a suíte inteira com o GTK real sob Xvfb, em 24 partes,
  com `HEFESTO_EXIGE_GTK_REAL=1`, e ali o pulo por falta de GTK reprova.

Em casa as 24 partes estavam verdes. No CI sobrou uma lista curta, que se
dividiu em quatro grupos por classe de causa. O critério: vermelho que passa em
casa e cai no CI é **ambiente até prova em contrário**, e a diferença exata tem
de ser reproduzida antes de qualquer cura.

## A bancada que reproduz o runner

- Um clone de um repositório local traz só o versionado: sem os documentos de
  processo e sem os scripts ignorados pelo git. É o que o runner vê.
- `HOME` e as pastas `XDG_*` desviadas **não bastam**: as variáveis da sessão
  gráfica (`XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP`, `DBUS_*`) atravessam e
  deixam passar vermelho real. A simulação roda com `env -i`.
- Bloquear o `gi` por um `sitecustomize` no `PYTHONPATH` reproduziu só 2 dos 6
  vermelhos do grupo do GTK: os filhos reescrevem o `PYTHONPATH` e acham o `gi`
  do sistema. A trava tem de morar num `.pth` do ambiente virtual, que vale para
  todo processo filho.
- Alguns vermelhos só aparecem com a **coleta inteira** de `tests/unit`, como o
  CI faz num processo só, rodando depois apenas os arquivos do grupo com `-k`.
- O runner público tem 4 vCPU; o grupo do tempo mediu com `taskset` em 4
  núcleos, `stress-ng` nos mesmos núcleos e, no gtk-real, o mesmo `--cov` do CI.
- As versões importam: o lint-test instala o `platformdirs` 4.12.0 pelo pip, o
  gtk-real usa o 4.11.11, a máquina de desenvolvimento tem o 4.2.0.

Com isso a bancada ficou **fiel ao CI**: no lint-test simulado (Python 3.12.14,
sem `gi`, `platformdirs` 4.12.0, sem bluez, `env -i`, coleta inteira), o clone
limpo deu 32 failed e 6 errors, o mesmo conjunto, nó a nó, dos 38 vermelhos do
log da perna 3.12.

## As causas e as curas

Nenhum vermelho pediu afrouxar asserção. Um só era defeito do produto.

### 1. Arquivo ignorado pelo git

- `test_o_dado_nao_mora_no_processo.py::test_toda_isencao_traz_a_razao_e_o_arquivo_existe`
  exigia `is_file()` de todo isento, e `scripts/check_colisao_de_sprints.py` é
  ignorado. A cura o partiu em `test_toda_isencao_traz_a_razao` e
  `test_todo_arquivo_isento_existe`, e é o segundo que leva o marcador.
- Três testes do portão que confere o `PYTHONPATH` de cada árvore de trabalho
  liam o script de despacho ignorado e caíam com `FileNotFoundError`.

**Cura:** o marcador que a casa já tinha, `pytest.mark.insumo_fora_do_git`. Ele
pula só quando o arquivo falta **e** o `.gitignore` explica a ausência, e escreve
a linha do `.gitignore` no motivo; sem essa linha, reprova em vez de pular. O
teste que misturava duas perguntas foi partido: a metade que pergunta ao git
(`.envrc-voo` não é versionado) roda em toda árvore. O portão local que cobre o
resto é `scripts/rodar-a-suite.sh` na árvore de integração, que recebe os
scripts ignorados antes de medir.

### 2. A chave que dependia da versão do Python

`scripts/check_a_tela_nao_confessa.py` montava a chave da `SEM_LETRA` com
`ast.unparse`, e as aspas de f-string aninhada saem diferentes por versão: o
3.12.3 dá uma chave, o 3.10.21, o 3.11.16 e o 3.12.14 dão outra. O portão
reprovava nas três pernas do lint-test e passava no gtk-real.

**Cura:** a chave passa a ser `ast.get_source_segment`, o texto como está no
fonte (`scripts/check_a_tela_nao_confessa.py:469`). Quatro chaves mudaram de
aspas, e a régua nova
`test_a_chave_sem_letra_e_o_trecho_do_fonte_em_qualquer_python` morde em
qualquer versão.

### 3. A sessão gráfica de quem roda

A linha `hefesto-ambiente` da aba Sistema sai de `a09_sistema._sessao()`, que
lê `XDG_SESSION_TYPE` e `XDG_CURRENT_DESKTOP`. No runner não há sessão, e o
travessão é a resposta honesta do produto. Em casa, a sessão gráfica vazava
para a suíte. **Cura:** a fixture declara a sessão com `monkeypatch` e esvazia o
cache `_BARATO`.

### 4. A máquina do runner

- **O `systemctl show` de unit ausente sai com 0** e imprime os defaults
  (`ProtectSystem=no`, `LoadState=not-found`). O runner não tem bluez, e a
  guarda `returncode != 0` nunca disparava. O bluez 5.72 do Ubuntu 24.04 traz
  `ProtectSystem=strict`, com a `bluetooth.service` idêntica byte a byte à do
  5.86 da máquina de desenvolvimento. **Cura:** a cópia byte a byte da unit em
  `tests/fixtures/systemd/de-terceiros/` (com `LEIA.md`) vira a hospedeira
  declarada, a tabela digitada sai, e `_sandbox_vivo` pergunta o `LoadState`
  (`tests/unit/test_bt_sandbox_cobre_o_que_os_ganchos_escrevem.py:158`). O
  confronto vivo com o systemd pula no runner, com o motivo escrito.
- **O `btmgmt info` classificado como escrita.** A escada dos adaptadores do
  `uninstall.sh` desce do sysfs para o `busctl tree org.bluez`, daí para o
  `btmgmt info` e por fim para o `hciconfig`. Em casa o sysfs responde antes; no
  runner a escada chega ao `btmgmt`, e o teste o tinha entre os que escrevem. O
  ensaio estava certo; a classificação, não. Caíam dois casos de
  `test_o_ensaio_do_uninstall_nao_escreve.py` e dois de
  `test_o_uninstall_acha_o_dkms_de_dois_kernels.py`. **Cura:** o `btmgmt` passa
  aos verbos que só leem, com `info`, e entra um caso determinístico (sysfs
  vazio, barramento sem bluez, `btmgmt` que conhece um adaptador) que exercita o
  terceiro degrau em toda máquina.
- **O `platformdirs` 4.12 recusa `XDG_RUNTIME_DIR` que não seja 0700** e cai no
  `/run/user/<uid>` de verdade. A fixture criava o diretório com o umask. Caíam
  sete testes de `test_single_instance.py`. **Achado grave:** com
  `platformdirs` ≥ 4.12 e o daemon de pé, `test_acquire_retorna_pid_atual`
  leria o `daemon.pid` real e mandaria `SIGTERM` ao daemon (o mecanismo foi
  reproduzido só na bancada isolada). **Cura:** o diretório nasce 0700
  (`tests/unit/test_single_instance.py:90`) e a fixture exige que o runtime
  resolvido fique dentro dele.

### 5. O GTK que falta fora do alcance da regra do conftest

Seis testes caíam no lint-test por quatro caminhos que
`pytest_runtest_makereport` não alcança:

| caminho | onde | sintoma no CI |
|---|---|---|
| processo filho | `test_os_dez_geradores_rodam.py` (aba01 a aba10), `test_os_leitores_do_glade_tem_dono.py` (aba05), `test_a_janela_nao_nasce_na_tela_dela.py` (o visor) | o pai só via `rc=1`, e o `AssertionError` não diz GTK |
| fixture emprestada de plugin que pulou | `test_o_botao_do_vulkan_diz_o_que_fez.py` (6 casos) | `fixture 'a09' not found`: o pytest descarta calado o plugin que pulou |
| stub no lugar da classe | `test_status_o_modo_compacto_tem_dono.py` | lia a docstring do stub sem GTK do `controller_card.py` |
| fallback de propósito | `test_a_06_nao_manda_para_o_vazio.py` | `_nome_do_botao` cai no id cru; só rodava por causa da poluição da coleta |

**Curas:** `repassar_a_falta_do_gtk` (`tests/conftest.py:2461`) transforma a
última linha do traceback do filho na mesma exceção no pai, e o próprio
`_falta_o_gtk` decide; `pytest_itemcollected` (`tests/conftest.py:2498`) faz
quem pede fixture a um plugin que pulou pular com o motivo do plugin; a
docstring do card passa a ser lida do fonte por AST (ganhou cobertura no
lint-test em vez de pular); e o teste da aba 06 importa o dono do nome
(`input_actions`). Um erro de verdade injetado no `aba01.py` continua
reprovando nos dois ambientes: o repasse não esconde defeito que não seja do
GTK. O bloco novo mora antes da seção `PARIDADE-BYTE-01` do conftest porque a
primeira posição deslocava uma citação `conftest.py:N` e derrubava
`test_portao_o_par_com_metade_ligada`.

Resultado do grupo: de 14 failed + 6 errors na coleta inteira para 0.

### 6. O tempo

- **`test_daemon_lifecycle.py::test_borda_de_queda_limpa_o_estado_publicado` —
  defeito do produto.** No `_poll_loop`, a queda que chega pela leitura que
  levanta (`poll_read_failed`) publicava `CONTROLLER_DISCONNECTED` sem limpar o
  store nem o `_last_state`: o daemon seguia dizendo controle conectado, por BT,
  com 80%, numa mesa vazia. **Cura:** um dono só para as duas portas da queda,
  `esquecer_a_leitura_publicada`
  (`src/hefesto_dualsense4unix/daemon/lifecycle.py:5822`, chamado em `:5942` e
  `:5968`). O dublê também era frouxo: o `FakeController` voltava no primeiro
  `connect()`, e a primeira sonda do `reconnect_loop` o religava durante o boot.
  Só com a cura do produto, a régua ainda reprovava 7/10 (lint) e 5/10 (gtk)
  sob carga; por isso o dublê também mudou.
- **`test_o_gesto_de_pareamento.py::test_fechar_derruba_a_varredura` e
  `test_a_ponte_devolve_os_candidatos.py::test_a_varredura_cai_junto_com_a_ponte`
  — o dublê.** O `bluetoothctl` de mentira marca a varredura num arquivo que só
  o `trap` de EXIT apaga, e o bash não corre esse `trap` sempre sob a sequência
  de sinais do GNU `timeout`: 2 em 100 com a sequência inteira, 0 em 100 com
  cada sinal sozinho. Em todas as voltas vermelhas nenhum processo sobrou; só o
  arquivo. **Cura:** a régua pergunta pelo processo, não pelo arquivo, e espera
  com prazo.
- **`test_o_cartao_diz_se_o_som_tem_para_onde_ir.py::TestOSeloDoAltoFalante::test_o_canal_parado_nao_desliga_o_selo`
  — a régua media um instante.** A fixture escrevia no cache e deixava o
  relógio da `_camada_1` vencido; a thread de renovação limpava o `_SONO` e o
  selo saía errado. A cobertura do gtk-real desacelera o fio principal, e por
  isso a parte 13 era verde em casa e vermelha no CI. **Cura:** a fixture
  adianta o relógio.
- **A divisão da suíte dependia do idioma.** `scripts/rodar-a-suite.sh`
  ordenava a lista com o `sort` do idioma de quem roda, e em pt_BR as partes
  diferiam das do runner. **Cura:** `LC_ALL=C` (`scripts/rodar-a-suite.sh:50`).

### 7. O vermelho que os grupos não viram

Os grupos leram só o log da perna 3.12. As pernas 3.10 e 3.11 também reprovavam
`test_toda_citacao_de_linha_em_comentario_de_codigo_confere`. **Causa:** no 3.12
o `tokenize` parte a f-string em `FSTRING_START/MIDDLE/END`, e a régua deixava
de ver o texto dela: o 3.12 lia 648 citações, o 3.10 e o 3.11 liam 667. Duas das
19 invisíveis tinham envelhecido, em `aba06.py` e `aba10.py`. **Cura:** a régua
conta o `FSTRING_MIDDLE` como prosa
(`tests/unit/test_portao_o_par_com_metade_ligada.py:1044`), as quatro versões
leem as mesmas 667, nas mesmas linhas, e as duas citações foram reapontadas à
mão, com uma régua nova que morde no 3.12. A cura regera
`mockup/06-navegacao.html` e `mockup/10-perfis.html` e publica as páginas 06 e
10 (duas linhas de prosa escondidas pelo produto).

## A contraprova

Cada um dos 18 diffs dos grupos teve a mordida refeita, e todas reprovaram como
deviam. Nenhum afrouxa régua que mede algo verdadeiro, nenhum troca a leitura
da máquina por um pulo calado, nenhum quebra na máquina de desenvolvimento. O
19º, o da seção 7, foi medido nos três ambientes.

| ambiente | antes | com os 19 diffs e o fecho |
|---|---|---|
| lint 3.10, 3.11 e 3.12.14 (grupos e vizinhos) | 31 failed + 6 errors (3.10) | 0 failed, 318 passed nas três |
| lint 3.12.14, coleta inteira | 32 failed + 6 errors | 0 failed, 346 passed |
| gtk-real (grupos, vizinhos e 53 arquivos do entorno) | 11 dos 13 do log (2 são de tempo) | 1431 passed |
| máquina de desenvolvimento (com os arquivos ignorados, bluez, sessão gráfica e daemon de pé) | 524 passed, 0 failed | 1460 passed |

As duas falhas que sobraram no gtk-real e na máquina de desenvolvimento eram de
`tests/unit/test_o_portao_declara_o_interpretador.py` e vinham da bancada sem
`.venv`; com a `.venv` ligada, 8 passed.

**A ordem de aplicação importa.** A cura do `lifecycle.py` desloca quatro
citações `lifecycle.py:N`, e `test_portao_o_par_com_metade_ligada` fica vermelho
até o reapontamento. O fecho é, nesta ordem: `scripts/reapontar-citacoes.py
--escrever`, `scripts/gerar-mapa.py` e o gerador do índice HTML (sem o último, o
`--check` do lint-test reprova — medido). Um commit por diff: primeiro réguas e dublês
(com o repasse do conftest antes dos que o chamam), depois a cura do produto, a
da seção 7 e o fecho.

## O que ficou aberto

- **F1 — a poluição de `sys.modules` vazou**, contra o que o resumo do lint-test
  afirma. Sete arquivos deixam `app.actions.*` presos a um `gi` falso até o fim
  da sessão: `test_auto01`, `test_daemon_status_matrix`,
  `test_mode_transition_um_dono`, `test_p10…`, `test_rumble_actions`,
  `test_status_actions_reconnect` e `test_triggers_actions`. Testes que sozinhos
  pulam passam a rodar contra um GTK de papel (13 casos de
  `test_a_aba_sistema_para_de_falar_pelo_desenho` só passam na coleta inteira),
  e `test_steam_input_honestidade.py` só coleta no lint-test por causa disso.
- **F2 — a sessão gráfica de quem roda atravessa a suíte.**
- **F3 — a suíte de casa usa o `XDG_RUNTIME_DIR` real.** Com o `platformdirs`
  novo que um `pip install -e .[dev]` traz, a suíte de qualquer pessoa pode
  chegar ao `daemon.pid` de verdade. É a frente que mais pesa para outra máquina
  reproduzir a suíte.
- **F4 — o `FakeController` compartilhado é mais frouxo que o backend real.**
- **F5 — falta teto de tempo por teste e por job no lint-test, e há testes de
  sono fixo.** A bancada viu uma trava única no 3.10, em
  `test_connected_event_publicado_no_start`, que não voltou em 23 corridas; sem
  teto, uma trava dessas seguraria o job até o limite de 6 h do GitHub sem dizer
  onde. Dois testes de sono fixo caíram sob carga, alheios às curas.
- **O confronto vivo da unit do bluez pula no runner.** A contraprova recomendou
  mantê-lo: é o único alarme para quando o bluez da máquina de desenvolvimento
  mudar o sandbox. A decisão ficou pendente.

As cinco frentes pedem a suíte inteira.
