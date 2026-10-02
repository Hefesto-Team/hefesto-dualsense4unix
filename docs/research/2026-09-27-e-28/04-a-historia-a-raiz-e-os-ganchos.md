# A história sem rastro, a raiz do repositório e os ganchos obrigatórios

O que se mediu em 27/09/2026 sobre o rastro de ferramenta de automação no GitHub, na história, na raiz e no pacote, e sobre as travas de máquina e de git que deveriam segurá-lo.

> **Como ler.** Os números são os de 27/09. Parte da limpeza da raiz entrou no
> `dev` em 28/09 (o §5 do [documento 01](01-a-onda-de-28-09-o-modo-o-som-o-salvar-e-a-raiz.md);
> `git log --since=2026-09-28 --format='%h %s'` diz o resto); onde a árvore de
> hoje já difere, vale a árvore. As sprints se citam pelo ID.

## 1. A barra de contribuidores

**O que se viu:** a barra «Contributors» do repositório lista três contas, e uma
delas é a conta da ferramenta de automação. Nenhum outro instrumento do GitHub
concorda: a API REST, o Insights recalculado no dia e o GraphQL dos autores e
coautores dos 3.919 commits do `dev` dão **duas pessoas** (3.680 e 239 commits).

**A causa:** 30 commits de 02 a 06/09 levavam um trailer de coautoria com o
endereço da ferramenta. Entraram no `dev` do upstream em **13/09 às 18h51 UTC** (o
push de 08/09 foi para o fork pessoal, e não para o upstream). A reescrita de 15/09
os tirou dos ramos, mas o GitHub continua a servi-los por três caminhos:

- `refs/pull/117/head` e `refs/pull/118/head`, duas PRs do dependabot fechadas sem
  merge, abertas sobre a história velha (a #117 em 24/08, a #118 em 14/09);
- seis topos velhos do `dev`, de 13 a 15/09, servidos pelo SHA e apontados pela
  página «Activity»;
- os forks, que servem os mesmos objetos.

A barra é uma contagem guardada que soma coautores, e não se refez em 12 dias.

**Fatos errados, substituídos:**

- «o `.mailmap` cura a barra»: não cura. O GitHub não lê `.mailmap`, e o
  `mailmap` do git não reescreve objeto nem trailer;
- «duas pessoas» (15/09) media a API REST, que nunca mostra coautor. Quem mede
  a barra é o fragmento `contributors_list` da página;
- a data de entrada dos 30 no upstream é 13/09, não 08/09.

**A cura é o suporte do GitHub, não uma reescrita.** Um filter-repo com a receita
do trailer, da sessão, do rodapé de geração e da identidade da ferramenta, sobre
os ramos e as 62 tags, muda **1 de 3.940** commits (a ponta do dependabot, só pela
assinatura) e **0 de 2.344** no fork: o que o GitHub recebe já não tem esse rastro.
O mesmo filter-repo num mirror com as `refs/pull` reescreve **4.829 de 7.661** e
leva o `dev` junto, sem ganho nenhum.

O chamado ao suporte pede quatro coisas: desreferenciar as PRs afetadas (64 se
houver reescrita, 2 se não houver), rodar o GC, apagar as visões em cache dos topos
velhos e reconstruir os contribuidores. Vai uma vez só, depois da reescrita, se
ela acontecer. A verificação é o fragmento da barra devolver só duas contas.

## 2. O rastro que sobra em público, fora da barra

A conferência achou rastro em lugares que nenhuma limpeza por commit alcança:

| onde | o que | cura proposta |
| --- | --- | --- |
| anotações e logs do Actions, legíveis sem login | «tem trailer de coautoria…» 30 vezes (execução 34775937447 do upstream, 34304522063 do fork); 176 execuções do `anonymity-check`; retenção de 90 dias | apagar as execuções depois que o portão de nome neutro substituir o `anonymity-check` |
| corpos de PR | rodapé de geração da ferramenta em 9 PRs (#67, #99, #101–#107); cerca de 20 com o checklist do modelo antigo de PR | editar e apagar a revisão antiga |
| notas de release | 5 releases da série 2.x citam a memória da ferramenta | reescrever pelo CHANGELOG novo |
| label de issue | uma label de tarefa automatizada em 54 issues (14 abertas) | apagar a label |
| tags | `v0.9.4.5` (a Latest) tem 19 arquivos que nomeiam a ferramenta; o «Source code» das releases sai das tags | reescrever as tags junto, ou release nova e apagar as antigas |
| fork pessoal público | ramo padrão é o `main` de 21/08, com 19 arquivos que nomeiam a ferramenta | apagar o fork, ou empurrar o `dev` limpo para o `main` dele |
| `Hefesto-Team/Forja` | arquivo de instruções de ferramenta na raiz | pergunta aos mantenedores |
| organização | o aplicativo da ferramenta instalado em 27/09 às 15h36, com escrita em código, PRs e Actions | desinstalar, se não for de uso; só uma regra de servidor alcança sessões na nuvem |

Os sdists antigos (`v0.1.0`, `v3.0.0`, `v0.9.4.3`, `v0.9.4.5`) levavam
arquivo de instruções e até 458 caminhos da pasta de processo. O `.deb` da
`v0.9.4.5` não leva essa pasta. Quem varrer artefatos exclui o
`site-packages` de terceiros.

## 3. A história publicada e a decisão de reescrever

Nas mensagens de `dev`, `main` e tags do upstream, **50 commits** têm rastro
explícito: 31 com o nome do modelo (14 deles merges de ramos de voo com o nome
no sufixo), 8 com a sigla da tecnologia, 5 com o nome do papel de sessão filha,
5 que designam a ferramenta, e 2 do mesmo dia 20/04 que citam o nome do arquivo de
instruções. Além deles, 279 usam o vocabulário de papel do processo, 143 o do
despacho, e 170 merges levam no assunto o nome de árvore que a ferramenta gera
(seção 7).

**Qualquer reescrita de mensagem troca os 3.940 SHAs e as 62 tags**, porque o
primeiro commit mudado é a raiz, de 20/04 (a conferência mediu 3.917 de 3.919 a
partir das duas mensagens de 20/04). As opções medidas:

- **A**, não reescrever: o chamado sai já; a trava de nível 1 só pode medir
  commit novo, senão fica vermelha para sempre;
- **B**, uma tabela de frases e o sufixo dos ramos: mantém os corpos;
- **C**, só o assunto: tira também o vocabulário de processo, mas apaga **3.410
  corpos** com decisão medida.

**A escolha é dos mantenedores** (`A-HISTORIA-REESCRITA-UMA-VEZ-SO-01`). Se
houver reescrita, é **uma só**, num fecho sem sessão rodando, e junta a mensagem e,
se decidido, o conteúdo.

### As armadilhas medidas no ensaio

- **O resultado depende do que está no clone.** Com as `refs/pull` ou com as
  branches locais presentes, o `dev` reescrito sai diferente (com as branches
  locais, em **1.577 commits**), porque linhas «cherry picked from» e prosa citam SHAs que só existem ali. Regra:
  uma corrida só, sobre a união, nunca com `refs/pull`; com
  `--preserve-commit-hashes` nas duas corridas o `dev` sai idêntico.
- **As quatro provas passam** em todos os ensaios: árvore idêntica em 100% dos
  pares, autor, datas e ordem iguais, tags preservadas. Nada assinado se perde no
  que se empurra (só a ponta do dependabot tem assinatura).
- **O filter-repo 2.38 cria `refs/replace` por padrão** (`update-and-add`): é daí
  que vêm as 517 do repositório local. Use `--replace-refs delete-no-add`.
- **Um callback por caminho relativo errado passa calado:** o `cat` falhou, o
  filter-repo recebeu corpo vazio, terminou em «Completely finished» e mudou 1
  commit. Use caminho absoluto e confira o `commit-map`.
- **`git bundle --all` não guarda os stashes anteriores nem o HEAD destacado das
  worktrees.** O backup é um repositório nu com `refs/backup/*` para cada um.
- **Empurrar:** refspec explícita, `--force-with-lease` por ref, nunca `--mirror`
  (levaria as `refs/replace`), nunca `--no-verify`.
- **As worktrees migram sem mudar um byte**, porque as árvores são iguais: uma
  transação `update-ref --stdin` montada do mapa de refs, com o valor velho como
  guarda.

### O que quebra fora do git

- `tests/unit/test_as_fotos_acompanham_a_versao.py` aceita a família de fotos
  atrasada só quando o SHA do último commit de tela está em
  `docs/usage/assets/CONFERIDO-EM.txt`. Depois da reescrita o SHA muda e a régua
  reprova. Um commit de remapeamento por cima a devolve ao verde.
- **465 citações de SHA** em 188 arquivos versionados: 337 já estavam mortas desde
  15/09 (só as `refs/pull` as seguravam) e 128 morrem na reescrita. Nenhum código
  pergunta ao git por SHA fixo. O remapeamento segue a cadeia de mapas
  (agosto → 15/09 → a nova) e exclui os hashes do kernel em `docs/protocol`
  (`AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA-01`, por último).

## 4. A raiz e o que o pacote instala

**`src/hefesto` não existe.** É o GitHub encolhendo `src/hefesto_dualsense4unix`
numa linha, e esse é o produto inteiro (o pacote do `pyproject.toml`, os dois
executáveis, os 401 arquivos do wheel). Fica.

O que se mediu dentro do wheel, construído de `git archive`:

- três exportações `*.dc.html` de uma ferramenta de desenho, com frase de conversa
  dentro, entrando pelo include `src/hefesto_dualsense4unix/interface/paginas/*.html`;
  o produto já as ignorava (`src/hefesto_dualsense4unix/interface/onde.py`);
- 10 `pasted-*.png` da pasta de uploads da ferramenta de desenho, que ninguém usa;
- 20 menções ao arquivo de instruções da ferramenta, em 13 arquivos;
- **342 comentários HTML narrados em primeira pessoa** (213 KB) nas páginas
  publicadas. A origem são os geradores `src/hefesto_dualsense4unix/interface/abaNN.py`; cortar só ao
  publicar quebraria a comparação sha256 de `scripts/check_o_desenho_aprovado.py`,
  então a cura é no gerador (`O-CODIGO-SEM-NARRADOR-01`).

**O portão de anonimato tinha dois furos por desenho:** `scripts/check_anonymity.sh`
apagava o nome literal do arquivo de instruções antes do teste e excluía o
`.gitignore` da varredura. Por isso 90 linhas em 59 arquivos passavam.

**Os próprios portões eram a lista pública do que se escondia:** o nome e os
passos do `anonymity-check.yml` do CI, a lista de fornecedores em
`scripts/check_anonymity.sh`, os testes dele, o portão da história, o `.pre-commit-config.yaml`, o CONTRIBUTING,
o modelo de PR e um bloco do `.gitignore` com o nome da tecnologia no título.

### O que a conferência derrubou da proposta da raiz

| proposta | por que não | o que vale |
| --- | --- | --- |
| tirar `scripts/carimbo_da_casa.py` com os painéis | `scripts/gerar-mapa.py:72-73` o importa, e o portão `mapa-de-canais` morreria em `ImportError` | fica, ou o `scripts/gerar-mapa.py` absorve no mesmo commit |
| tirar `scripts/check_a_conferencia_dela.py` | é o portão do merge, por desenho (`tests/unit/test_portao_todo_portao_tem_chamador.py:68-70`) | trocar o nome, ou ir para os scripts ignorados que se copiam à integração |
| mover para `scripts/` as duas bancadas da raiz (a do mapa, em Streamlit, e o lançador da mesa de medição) | as duas acham a raiz pela própria pasta; movidas, apontam para `scripts/docs`, e os testes, que só leem o texto, ficam verdes | mudar a linha da raiz junto e abrir as duas depois do `git mv` |
| mover `run.sh` | o autostart da bandeja e o `./run.sh --smoke` do CI o chamam | fica na raiz |
| tirar `docs/data` do git | o produto lê em execução (`src/hefesto_dualsense4unix/integrations/canal_sem_imu.py:78`, `src/hefesto_dualsense4unix/integrations/cor_do_plastico.py:137`) | fica; só o nome `docs/data/decisoes-dela.csv` muda |
| mandar os padrões do `.gitignore` para `info/exclude` ou para o ignore global | o hatchling não lê nenhum dos dois: num ensaio o sdist empacotou o arquivo de instruções e a pasta de processo | `[tool.hatch.build.targets.sdist] only-include` no mesmo commit; as linhas só saem depois de o outro mantenedor ter os padrões no ignore global dele |

As outras mudanças da raiz, sem custo de produto: a pasta de código arquivado
(645 linhas mortas), o arquivo de dependências que ninguém lia (e já divergia:
não listava o WebKit2), as capturas HID para `tests/fixtures/hid/`, o lançador da
interface dentro do `run.sh --gui`, e o guia do rádio da sala movido para
`docs/usage/bluetooth-varios-adaptadores.md`, sem as seções da máquina pessoal.
Sprints: `A-RAIZ-SO-COM-O-PRODUTO-01`, `AS-PAGINAS-DE-PAINEL-SAEM-DO-GIT-01`,
`O-CODIGO-NAO-NOMEIA-A-FERRAMENTA-01`.

## 5. O README e os textos de quem usa

- **README:** voz de diário e dois fatos errados. Mandava instalar a `v0.9.4.5`
  (a janela GTK antiga, 3.152 commits atrás do `dev` cujas fotos ele mostra) e descrevia uma
  aba «Início» que não existe (a aba 1 é Jogar). Duas réguas obrigavam texto de
  dentro: o emblema de contagem de testes (`tests/unit/test_emblemas_do_readme.py`)
  e a contagem de parâmetros do `DaemonConfig`
  (`tests/unit/test_doc_verdade_02_contagens_derivadas.py`); mudam junto.
- **O README proposto perdeu** o que só ele ensinava: a variável dos plugins, o
  `systemctl --user` e o `journalctl --user`, o microfone por rádio, o 8BitDo em
  DirectInput. E nenhum dos dois avisava do Secure Boot, que `install.sh:1621-1629`
  diz deixar a máquina pior do que antes.
- **CHANGELOG:** 3.927 linhas de diário, com links para a pasta de processo (404 no
  GitHub). Proposta: Keep a Changelog, uma linha por mudança visível, menos de
  400 linhas; o metainfo do Flatpak (o texto da loja) e as notas de release saem
  dele.
- **Instalador e doctor:** 21 de 640 linhas de mensagem de `install.sh` e
  `uninstall.sh` levam ID de sprint, e 25 de 542 de `scripts/doctor.sh`. O passo
  diz o que faz; o ID fica no `git log`.
- **CONTRIBUTING, modelo de PR e SECURITY** descreviam a linha de montagem, e o
  SECURITY dava como suportada a 2.1.x. O NOTICE misturava atribuição legal com
  notas datadas.
- **`docs/usage`:** 23 páginas e cerca de 7.500 linhas, com páginas da janela
  aposentada e 17 links para a pasta de processo, que fica fora do git. Alvo:
  cerca de 17 páginas e 2.300 linhas.
- **`assets/`**, que o instalador copia para `/etc` e `/usr/src`, também leva
  referências de processo (a regra udev do touchpad, `assets/proton-pin.conf`,
  as units do vigia do Steam Input, o `hid-playstation.c` do DKMS). O `# doc:` das units
  é lido por uma régua, que muda junto.

Sprints: `O-README-E-OS-TEXTOS-DE-GENTE-01`, `AS-PAGINAS-DE-USO-FALAM-COM-QUEM-USA-01`.

## 6. As travas do git

**Os ganchos da máquina deixavam 8 de 15 cenários passarem com rastro indo ao
remoto:** isenção por SHA, ramo de rastreio velho, `refs/replace`, `push --mirror`,
tag anotada, committer, nome do autor e ramo de voo.

- **A isenção por SHA era a porta.** As 31 entradas de `hooks.anonimato.isento` no
  `.git/config` são exatamente os 31 commits sujos que o GitHub ainda serve. Das 31,
  **19 foram commits feitos pela própria ferramenta com
  `git -c core.hooksPath=/dev/null`**, quase todos com `git add -A`, em 04 e 06/09.
  A causa registrada antes, o cherry-pick, é fato errado: a causa dominante foi o
  gesto. Cura: tirar a isenção e remover as 31 entradas.
- **Ramo de rastreio velho** servia de salvo-conduto para o `--not --remotes` do
  pre-push. Cura: `git fetch --prune` e `fetch.prune true`. A conferência mostrou
  que tirar o `--not --remotes` barra o push legítimo de merge com commits de
  outras pessoas; a medida certa é contra o que o servidor tem (`git ls-remote`).
- **`refs/replace`:** gancho e portão leem através delas, e o push leva o
  original. Cura: `GIT_NO_REPLACE_OBJECTS=1` em todo gancho e régua.
- **As refs de checkpoint da ferramenta** nascem com os ganchos desligados; um
  gancho `reference-transaction` não as segura (rc=0). Um diretório de refs dela
  somente leitura (`chmod 555`) segura (rc=128), sem afetar commit, gc, fetch ou
  clone.
- **O gancho do repositório, encadeado pelo global, não roda em worktree**, e a
  árvore principal de trabalho é uma worktree: o global procura
  `$REPO_ROOT/.git/hooks/`, e ali o `.git` é um arquivo. O `scripts/hooks/pre-commit`
  está morto em toda worktree desde 01/09, e a corrida de CI de 27/09 16h16 caiu no
  `indice-html-publicado` que ele regeraria (relação lida no código, não
  reproduzida). Encadear pelo `--git-common-dir`
  reativaria um link para uma cópia de 01/09 (39 linhas diferentes da atual) que
  regera páginas e faz `git add` sozinho; a proposta que vale é o gancho global
  rodar o script de autoria da árvore quando ele existe e reprovar com «política
  não medida» quando falta.
- **HOME desviado** apaga os ganchos globais e mantém a identidade (ela vem do
  `.git/config`).
- **A mensagem de bloqueio do pre-push ensinava `--no-verify`**; o aviso de
  formato do commit-msg saía em 100% dos commits (no `dev` desde 20/09, 1.306 de
  1.321 usam `tipo(escopo):`, que ele não aceitava); e o pre-commit global desligava a
  checagem de espaço e o `py_compile` quando achava `.pre-commit-config.yaml`,
  com o framework ausente da máquina (`scripts/portoes.sh` declara a questão como
  decisão em aberto).

**A régua de autoria proposta** (`A-AUTORIA-SE-MEDE-PELA-LISTA-DE-QUEM-PODE-01`):
a autoria se confere pelo `.mailmap`, que é a lista de quem pode assinar, sem
nomear ninguém de fora. A conferência derrubou três partes dela:

- **a lista de termos em hash se reverte** com um dicionário de 50 palavras (19 de
  21 no nível 1, 20 de 20 no nível 2, em menos de 1 s), porque o sal mora no
  arquivo. O vocabulário fica fora do repositório (gancho da máquina e segredo do
  CI); onde o segredo não chega, o passo diz NÃO MEDIDO, nunca verde;
- **o nível 2 barra o próprio produto:** o import do módulo de pareamento do BlueZ
  e a forma verbal em maiúsculas usada no estilo da casa. Ele sai do gancho e do
  CI;
- **a regra de quem pode** barra contribuição de fora e os aliases que o próprio
  `.mailmap` declara (commits feitos pela interface web do GitHub). Decisão dos
  mantenedores: ou não há PR de fora e o CONTRIBUTING diz isso, ou quem contribui
  entra no `.mailmap`.

**O `dev` está sem proteção** (a API de proteção devolve 404), o único ruleset
está desativado, e só o `release.yml` do CI barra CI vermelho. O ruleset que
exige o check de autoria, como escrito, nunca ficaria verde: o job de autoria
proposto só dispara em push para `dev` e `main`, e o pre-push proposto recusa o
ramo de fecho. Ele é a única trava que alcança outra máquina e sessões na nuvem.

## 7. Os ganchos da ferramenta de automação

Esta parte mede a configuração da ferramenta, que mora fora do repositório. Ela
fica registrada aqui porque os defeitos que ela deixou passar estão no produto e
na história.

### O que a madrugada de 26–27/09 deixou passar

| o que | medida |
| --- | --- |
| endereço de controle na saída | 6 vezes em 17 h, sempre na forma colada; a máscara era escrita à mão ou faltava, e a da casa não cobre a forma D-Bus (`dev_XX_…`) nem os bytes invertidos |
| duas sessões na mesma árvore de integração | duas vezes (14h14–14h22 e 15h11–15h28), notadas por acaso |
| CI vermelho empurrado | **61 corridas vermelhas** seguidas no `dev` desde 26/08; o último verde é de 22/08. Em 26/09, 8 pushes depois de ler o vermelho |
| sessão gráfica caída | 5 pânicos do compositor; o daemon foi reiniciado às 05h28 sem causa escrita, 7 min depois da primeira queda |
| sucesso lido pelo eixo errado | às 16h16, «pads no uhid» foi lido como sucesso; era o Freestyle (modo Xbox) desfeito, porque a promoção `upgrade_primary_vpad_to_uhid` pergunta só a máscara |
| senha de administrador | entrou numa mensagem e num comando; no histórico, a forma `echo <senha> \| sudo -S` aparece 96 vezes entre 02 e 19/09 |
| sprint fechada sem prova | a do pad virtual pedia 20 voltas e fez 5; a `O-MODO-XBOX-NAO-E-QUEDA-01` adiou a prova do modo Xbox; nenhuma disse o CI |
| trailer de coautoria | em 1.181 de 1.465 comandos de commit entre 20 e 27/09; o commit-msg da máquina o apagou em silêncio 1.300 vezes; parou às 15h26 de 27/09, com a atribuição vazia na configuração. Os 307 commits de 26–27/09 estão limpos |
| rastro que o commit-msg não vê | 170 merges sem `-m` com o nome de árvore que a ferramenta gera; merges com o nome do modelo no ramo; texto de PR e issue pelo `gh`, que não passa por gancho nenhum |

**Fato errado, substituído:** «o CI está vermelho desde 26/09 14h27». São 61
corridas desde 26/08, e 14h27 é hora UTC.

A decisão do Freestyle mudou sem registro único: a `D-2709` revoga a
`D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA`, mas o CSV de decisões ainda a
trazia sem revogação quando a pergunta voltou, às 16h40. No fim da rodada, o
produto já estava no `dev` e a revogação, no CSV.

### O que existia

Nenhuma trava. A configuração não tinha ganchos nem regra de recusa; as duas
regras que existiam só valiam no modo automático, e 26–27/09 rodaram 100% no
modo que pula permissões. **Um deny de gancho vence esse modo** (lido no
binário), e é por isso que o gancho serve. A configuração voltou sozinha ao modo
automático às 15h15m47s, sem chamada de ferramenta nenhuma; o provável gravador é
um comando de configuração da própria ferramenta aberto às 15h12. Uma trava
registrada ali some do mesmo jeito, e por isso a conferência na abertura da
sessão e no self-heal é obrigatória.

### O que se propôs, e o que a conferência corrigiu

As quatro frentes deram protótipos mordidos: 70/70 casos e 13 mutantes no
inventário; 83 regras catalogadas (45 mecânicas, 16 de julgamento, 22 fora de
gancho) com 203/203 na bateria; o gancho do rastro no ato com 78/78 casos e 21/21
mutantes. O replay de 30.216 chamadas reais de 25 a 27/09 recusou 575, todas pelo
trailer, e zero depois das 15h26 de 27/09. Custo: 24 a 42 ms de mediana por
chamada.

**Como estavam escritas, não se instalam.** De 62 casos da conferência, 25 barram
fluxo legítimo, 19 contornos funcionam e 7 corrompem dado:

- o envoltório de escopo matava a posse da árvore (gravava o PID do envoltório,
  que morre) e a guarda da configuração fora do projeto;
- `matcher`, `async` ou `if` na configuração desligavam a trava sem nenhuma
  guarda ver; a liberação por `touch` estava ao alcance da sessão, e a mensagem
  ensinava o comando;
- a máscara corrompia MM:SS, PID, UUID, o report `0x31` e o `btmon`, e recusava a
  palavra citada em `grep` e `git log`. Corrigida: 7 de 7 formas, 0 de 5
  corrupções; um SHA de 12 hex segue mascarado, de propósito (um SHA truncado se
  relê, um endereço vazado não);
- a leitura mascarada de arquivo mudava 363 linhas de 121 arquivos versionados, e
  a edição seguinte não casaria. Só a linha com endereço se mascara;
- a regra dos recibos recusaria todo push, porque nenhum script escreve recibo.
  Ela dorme até o `scripts/portoes.sh` e o `scripts/rodar-a-suite.sh` escreverem
  (`O-PUSH-SO-COM-O-RECIBO-DOS-PORTOES-01`);
- o disjuntor recusava quem **lê** a causa e destravava com qualquer texto. Passa
  a olhar só o gesto que **roda** (restart, install, Steam, ensaio);
- a regra de sprint feita barrava nota em 371 de 377 sprints feitas. Vale só na
  **transição** para `feita`;
- a checagem no fim de uma sessão filha media a árvore principal: 260 de 300
  delas têm o diretório de trabalho ali, e trabalham noutra por caminho absoluto;
- a cobrança no fim da resposta pesaria em 13% dos turnos (195 de 1.502); fica
  uma semana só registrando antes de ligar.

As correções, provadas em cópia, dão 52 de 52 casos certos. No dia real, os 15
eventos dos vazamentos seguem recusados. Cinco processos por comando somam 60 a
68 ms; a proposta é um despachante único.

**A ordem:** `A-TRAVA-DA-MAQUINA-DELA-01` (pré-condição) → `A-VIGIA-DAS-TRAVAS-01`
→ em paralelo `O-DESPACHANTE-DAS-REGRAS-DA-CASA-01`, `O-RASTRO-BARRADO-NO-ATO-01`
e `OS-GANCHOS-DO-GIT-NAO-ENSINAM-O-CONTORNO-01` → em paralelo
`A-SENHA-SO-PASSA-PELO-ASKPASS-01`, `O-ENDERECO-NUNCA-CHEGA-A-CONVERSA-01` e
`A-ARVORE-TEM-UMA-SESSAO-SO-01` → `O-FEITO-SO-COM-A-PROVA-01` (uma semana em
registro) → `A-GUARDA-FECHA-A-PORTA-01`, armada pela mantenedora no terminal dela;
daí em diante, mudar trava é gesto dela. Fora das ondas:
`O-PUSH-SO-COM-O-RECIBO-DOS-PORTOES-01` (depois da autoria) e
`O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01` (depois da
`O-MODO-XBOX-NAO-E-QUEDA-02`).

## O que ficou aberto

- **Reescrever ou não a história** (A, B ou C), e a redação da tabela de frases:
  decisão dos mantenedores. Com ela, o número de PRs no chamado ao suporte.
- **O chamado ao suporte do GitHub** e a reconferência da barra.
- **Apagar as execuções do Actions** com o texto antigo, o fork pessoal, as tags e
  releases antigas; o destino do `Hefesto-Team/Forja` e do aplicativo instalado na
  organização.
- **Contribuição de fora e os aliases do `.mailmap`**: a regra proposta barra os
  dois (os aliases, também o portão de hoje).
- **Os rulesets** do `dev` e do `main`, com o check de autoria corrigido para
  disparar no ramo de fecho.
- **`packaging/debian/control`** não declara `gir1.2-webkit2-4.1`, que a interface
  exige. Hipótese: a janela não abre num `.deb` em sistema limpo; falta instalar
  num contêiner e medir.
- **`packaging/cosmic-applet`**, aposentado em 19/09 com o código mantido, ainda
  usa um app-id pessoal. Tirar ou não é pergunta.
- **O sha256 do «Source code»** das releases muda com a reescrita (o cabeçalho pax
  grava o commit): hipótese, não medida.
- **A pré-condição de fora:** uma linha de `tests/conftest.py` pertence a sprints
  de outra leva (`VERDE-NAO-E-PROVA-01`, `O-CI-DA-DEV-VOLTA-A-VERDE-01`,
  `RELEASE-NO-CLONE-LIMPO-01`); sem ela limpa, a régua de autoria não fica verde.
- **Nos ganchos, só a instalação mede:** se a troca da saída de um comando chega
  ao texto lido e à tela, a entrada do evento de criação de worktree, e o cwd de
  uma sessão filha numa worktree de rodada.
- **Sem trava ainda:** a leitura de «pads no uhid» sem perguntar o modo, a senha
  que chega pela mensagem, 496 de 497 escritas soltas no diretório temporário feitas por shell, e
  a configuração regravada pelo comando de configuração da própria ferramenta.
