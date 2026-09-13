# F1-REMAPEAR-02 — a entrega do agente IMPLEMENTA (13/09/2026)

Sprint: [F1-REMAPEAR-02](../../sprints/2026-09-13-F1-REMAPEAR-02-as-seis-linhas-que-a-troca-nao-alcanca-e-o-ps-do-boot.md),
lote `1309-onda2`, branch `voo/F1-REMAPEAR-02-opus`, nascida de `onda/1309` = `e1c7d96b`
(conferido antes de tudo). O estudo é a [entrega da F1-REMAPEAR](F1-REMAPEAR-opus.md).
Sem aparelho: `bancada: false`, toda prova é com dublê, e o daemon dela não foi
subido nem reiniciado.

## O que mudou

**As seis listas que a troca não alcança nascem apagadas** — a direção do L3 e do
R3, o PS e as três regiões do touchpad (os botões de `core/acoes_de_botao.BOTOES`
que não estão em `remapeamento_de_botao.REMAPEAVEIS`).

- `interface/aba06.py`: `drop` ganhou `apagado`, que emite `disabled`; a nova
  `_lista_da_troca` dá às dezesseis o gesto, a linha e o endereço de sempre, e às
  seis só a linha, o `disabled` e a opção «— Sem troca —». O `data-linha` fica,
  porque a `forma` do «Guardar» continua sabendo de todas as linhas. A folha da
  06 ganhou `.campo-linha:disabled` com a cara do apagado da casa (borda sutil,
  texto mudo, `cursor:not-allowed`) e o `:hover` que não acende o roxo.
- **Por que `disabled` e não só tinta**: com `pointer-events:none` a lista ainda
  recebe foco pelo teclado e muda pelas setas, e a escolha voltaria à `forma`.
  Medido no Chrome depois da cura: o foco não entra na linha do PS.
- A decisão é de quem coordena, por delegação (§D da sprint), sobre a regra do
  apagado que ela deu na 06-Q1 — a palavra está em
  `docs/process/2026-09-05-AS-QUARENTA-E-UMA-DECISOES-DELA.md` e citada no bloco
  do portão de modo da folha da 06: *"o switch fica apagado (não clicável) MAS
  mostra o estado real"*. O docstring de `drop` dizia «nenhum travado» (falas
  [55], [57] e [91]); ganhou a nota datada que nomeia a exceção e o dono.
- A autoconferência do gerador passou a cobrar 16 listas com gesto (e o
  `data-linha` delas igual a `REMAPEAVEIS`), 6 apagadas (as que o motor recusa,
  cada uma só com «— Sem troca —») e nenhuma lista fora das duas contas.
- `mockup/06-navegacao.html` regerado e publicado com
  `check_o_desenho_aprovado.py --publicar 06` («1 mudou de fato»).

**O «Guardar» só aceita as seis em «— Sem troca —»** — `a06_navegacao.guardar_remapeamento`
recusa, antes do motor, a forma que traga outra coisa nelas. A guarda existe
porque o motor deixa passar a troca por si mesmo (o PS para «PS», a direção do
L3 para «L3 (direção)»): o `resolver` a apaga antes de conferir. A recusa do
motor fica logo abaixo. A frase é a do motor com os nomes da tela
(`_frase_da_troca`), e desde a FRASES-E-DICAS-01 ela vai só ao diário.

**O boot entrega o PS do perfil** — `daemon/connection.py::restore_last_profile`
passa `ps_action_sink=_canal_do_ps(daemon)`, o mesmo canal que
`gerente_do_daemon` passa às outras rotas. O `mouse_applier` e o `mode_applier`
continuam `None` (BUG-BOOT-RESTORE-FLIPS-EMULATION-01). **O achado foi medido
antes da cura**, com o roteiro de dublê que virou a régua: na base, o boot com um
perfil que dá `KEY_ESC` ao PS imprimiu `definir_acao_do_ps chamado com: []` e
`acao_do_ps_do_perfil(daemon): None`. Confirmado, a cura ficou.

**O arquivo não mudou de tamanho, de propósito**: 1530 linhas antes e depois.
`docs/data/mapa-controles.csv` e três arquivos de `src/` e `tests/` citam linhas
do `connection.py` por número, e o CSV não é desta sprint. O import entrou na
linha que já existia, e as três linhas do comentário novo mais a do argumento
foram pagas reescrevendo em linhas mais largas, palavra por palavra, os dois
comentários vizinhos (BUG-BOOT-RESTORE-FLIPS-EMULATION-01 e
FEAT-RUMBLE-POLICY-PROFILE-01). A distância que o comentário do
FEAT-ACOES-DE-BOTAO-01 cita («quinze linhas adiante») não mudou.
`validar-citacoes-de-linha.py --all`: `OK: 3291 citação(ões)`;
`test_portao_o_par_com_metade_ligada.py`: `16 passed`.

**As réguas:**

- `tests/unit/test_as_seis_linhas_fora_da_troca_ficam_apagadas.py` (nova, 15
  casos): a página na bancada e no publicado, a folha, o clique forçado no
  Chrome com o `BOOTSTRAP` do piloto (a Cruz é o controle do instrumento), o
  pacote com disco de mentira nas quatro formas de recusa e na que grava, e o
  motor recusando as seis;
- `tests/unit/test_o_boot_entrega_o_ps_do_perfil.py` (nova, 3 casos): o
  `restore_last_profile` de verdade, com dublê só nas bordas; o perfil que dá a
  tecla a entrega, o que não opina apaga a de antes, e o boot continua sem
  mouse e sem modo;
- `tests/unit/test_a_recusa_pisca_no_botao.py`: o caso 06 — a colisão (Cruz e
  Quadrado para o Círculo) no «Guardar» REAL da troca, clicado no WebKit oculto
  com as listas escritas na mesma chamada do clique; a recusa não pousa recado,
  nem frase visível, nem dica, nem `title`; o botão veste `hef-recusou` e o
  perde em `MS_DA_PISCADA`; a frase vai ao diário
  (`[gesto falhou] 06-navegacao.html · guardar-remapeamento: …`). A recusa
  acontece antes de qualquer leitura de perfil, e o disco é o de mentira da
  suíte;
- `tests/unit/test_migra_navegacao_13_o_remapeamento_botao_a_botao.py`: a
  página publicada tem 22 listas e só as dezesseis falam.

## Qual mordida prova

Roteiro próprio no rascunho: arranca, roda, devolve o arquivo byte a byte
(sha256 conferido), roda de novo — cada pytest com `PYTHONPYCACHEPREFIX` vazio,
pela armadilha do `.pyc` que a F1-REMAPEAR pagou. Antes das mordidas a
implementação foi commitada (`b396401e`); no fim, `git diff HEAD` vazio e
`git status` vazio.

```
M1a uma das seis volta a ser clicável no GERADOR (a linha do PS sem `apagado`)
   arrancada: rc=1  ERRO em 06-navegacao — decisão dela desfeita:
                    - as listas apagadas da troca são ['l3_direcao', 'r3_direcao',
                      'touchpad_left_press', 'touchpad_middle_press',
                      'touchpad_right_press'], e as que o motor recusa são
                      ['l3_direcao', 'ps', 'r3_direcao', …]
   devolvida: rc=0
M1b uma das seis volta a ser clicável na PÁGINA PUBLICADA (o PS sem `disabled`)
   arrancada: rc=1  AssertionError: a linha 'ps' da troca voltou a ser clicável
                    AssertionError: a lista 'ps' está habilitada
                    2 failed, 13 passed
   devolvida: rc=0  15 passed
M2  o `ps_action_sink` sai do boot
   arrancada: rc=1  AssertionError: o boot chamou `definir_acao_do_ps` com [] …
                    assert [] == ['KEY_ESC', None]
                    (e o terceiro: o gerente do boot sem `ps_action_sink`)
   devolvida: rc=0  3 passed
M3  a frase da recusa volta à tela da 06 (o piloto a pousa na página)
   arrancada: rc=1  AssertionError: 06-navegacao.html: a recusa pousou 1 recado(s)
                    na tela — é a caixa laranja que ela mandou parar de aparecer
                    FAILED …::test_a_recusa_nao_poe_frase_na_tela[06]
                    1 failed, 24 passed
   devolvida: rc=0  25 passed
M4  a guarda das seis sai de `guardar_remapeamento` (só o motor recusa)
   arrancada: rc=1  Failed: DID NOT RAISE RuntimeError  (duas vezes)
                    FAILED …[ps-por-si-mesmo]
                    FAILED …[l3-direcao-por-si-mesma]
                    2 failed, 13 passed
   devolvida: rc=0  15 passed
RESULTADO: 5 de 5 · git diff HEAD igual antes/depois (0 bytes) · status igual
```

A M3 mexeu no `hefesto_vivo.py`, que é `nao_toca`: a mutação durou a corrida e
foi devolvida pelo sha256; o commit não o toca.

**A foto** — a tela «Trocar os botões» publicada, num Chrome headless (a `--foto`
do piloto fotografa a aba, não a pop-up):
[antes](F1-REMAPEAR-02-ANTES-troca-de-botoes.png) ·
[depois](F1-REMAPEAR-02-DEPOIS-troca-de-botoes.png). A diferença visível é uma
só: as seis listas em cinza. Lido no DOM das duas páginas:

| | antes (`e1c7d96b`) | depois |
| --- | --- | --- |
| listas com `linha-de-troca` | 22 | 16 |
| listas `disabled` | 0 | 6, cursor `not-allowed`, texto `rgb(154, 158, 184)` |
| clique de ponteiro nas seis | chegou como `linha-de-troca` | recusado pelo navegador, nenhum gesto |
| foco pelo teclado na linha do PS | entrava | não entra |
| a `forma` do «Guardar» | 22 chaves | 22 chaves, as seis em «— Sem troca —» |

**Nenhum botão novo**, contado nas duas páginas publicadas: `<button` 12 e 12,
`<select` 63 e 63, `<a ` 37 e 37, `class="btn` 21 e 21, `title=` 46 e 46;
`data-gesto` foi de 95 a 89 — são os seis `linha-de-troca` que saíram.

**O clique no WebKit, oculto** — `hefesto_vivo.py --oculta --abre 06 --segundos
12 --prova-clique linha-de-troca,fechar-troca`, com
`HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, antes e depois: `gestos: 2 ·
aplicados: 2 · sem dono: 0`, sem Traceback, 119 tiques na 06. Os perfis dela
foram copiados antes da primeira corrida, e o md5 dos 159 arquivos saiu igual
depois de cada uma. O «Guardar» e o «Voltar ao padrão» não foram clicados no
WebKit contra o perfil dela; o «Guardar» só foi clicado dentro da régua, com o
disco de mentira.

**As réguas vizinhas**, rodadas depois da regeração: as dezessete
`test_a_06_*`, `test_a_aba_06_navegacao_fecha_as_linhas.py`,
`test_o_padrao_de_fabrica_cabe_na_tela_publicada.py`, a F1-REMAPEAR e a nova das
seis — `259 passed`; `test_a_recusa_pisca_no_botao.py` — `25 passed`; a do boot
e a da fábrica do gerente — `19 passed`. `ruff check src/ tests/`: `All checks
passed!`.

**Os portões inteiros**, com `git add -A` antes e esperados pelo PID (conferido
com `ps` que a corrida viva de outra árvore, a da DICA-DA-COR-01, não era
desta). A primeira volta deu `REPROVOU: 1 vermelho(s) de 60 -> acentuacao`: a
chave `opcoes` na régua nova das seis, cinco vezes, trocada por `rotulos`. A
segunda deu `TODOS VERDES — 60 portões.`, e a terceira, depois deste
parágrafo, é a que o commit leva.

## O que NÃO verifiquei

- **Nada no aparelho nem no daemon vivo.** O boot foi exercido com dublê
  (`StateStore` real, `_canal_do_ps` e `definir_acao_do_ps` reais, disco e
  aparelho de mentira). Que o `ps_solo` do daemon dela passe a digitar a tecla
  do perfil logo depois de um boot fica para a bancada (MESA-DE-QUATRO-01).
- **As outras frases de recusa da troca na 06.** Medi na tela só a colisão. O
  PS, a linha fora do alcance, o rótulo desconhecido, a forma ilegível, o igual
  ao perfil, o apagador e o padrão já sem troca saem pelo mesmo
  `Piloto._recusou_dizendo`, que a régua sem janela da FRASES-E-DICAS-01 prende
  ao diário — mas nenhuma delas foi clicada na página.
- **A lista apagada no WebKitGTK.** O `disabled`, o cursor e a cor foram lidos
  no Chrome; no WebKit o piloto só clicou a primeira lista (a da Cruz) e o
  fechar. A foto do WebKit é da aba, não da pop-up.
- **O leitor de tela e a navegação pelo controle** sobre as seis listas: não
  medi se o `disabled` as tira da ordem de foco do jeito que o controle navega a
  interface.
- **A suíte inteira** não rodou, por ordem do despacho.

## O que sobrou para o próximo

- **Quem costura regera as dez**: `mockup/06-navegacao.html` e
  `interface/paginas/06-navegacao.html` mudaram pelo gerador. Colisão provável
  com qualquer sprint da onda que regere a 06.
- **A lista apagada não diz por que não troca** — é o §R da sprint, o preço da
  ordem de 13/09: sem frase.
- **`docs/data/paridade-gtk-html.csv`, linha do gesto `guardar-remapeamento`**
  (fora da posse): continua certa, mas não diz que seis das linhas da tela nascem
  apagadas. Se a paridade quiser esse detalhe, é texto dela.
- **Para a SPECS-A-PROCEDENCIA-01**, pela chave do mapa: `entrada.botoes` do
  DualSense — a ação que o perfil dá ao PS passou a chegar ao atendente do
  `ps_solo` também no boot. Medido só no degrau MONTOU, com dublê, sem
  transporte.
