#!/usr/bin/env bash
# portoes.sh — A LISTA DE PORTÕES DESTA CASA, e ela é UMA SÓ.
#
# POR QUE ELE EXISTE, e o defeito é medido: até 25/08/2026 a lista de portões
# vivia em DOIS lugares — o bloco "Antes de fechar qualquer leva" do contrato
# da casa e os jobs do `.github/workflows/ci.yml`. Duas listas para a mesma
# coisa é o defeito que a regra do fato-errado existe para matar, e ele COBROU:
# o `validar-caducos.py` roda no CI e NÃO estava no bloco local, e foi assim
# que um literal caduco atravessou uma leva inteira e só apareceu no vermelho
# do CI.
#
# A partir daqui a lista mora AQUI, em `_LISTA`, versionada e viajando junto
# com qualquer árvore de trabalho. O contrato da casa NÃO é versionado, então
# ele não pode ser a fonte: uma árvore nova nasce sem ele.
#
# E A LISTA TEM PORTÃO PRÓPRIO: `tests/unit/test_portao_a_lista_de_portoes_e_uma_so.py`
# compara esta tabela com o que o `ci.yml` roda e REPROVA na divergência. Quem
# acrescentar um job ao CI sem acrescentar a linha aqui é barrado nomeando o
# script que ficou de fora — que é exatamente o caso do `validar-caducos.py`,
# agora impossível de repetir.
#
# PORTÃO DECLARADO E AUSENTE DA ÁRVORE SAI rc=1 NOMEANDO, nunca em silêncio.
# É a cicatriz do `validar-acentuacao.py --check-file`, que devolvia rc=0 contra
# arquivo que não existe: portão cego é pior que portão nenhum.
#
# Uso:
#   scripts/portoes.sh              a leva inteira (rápidos + completos)
#   scripts/portoes.sh --rapido     só a camada rápida (50 portões: 69 a 82 s em série, 19 a 29 s em paralelo)
#   scripts/portoes.sh --suite      acrescenta a suíte de testes
#   scripts/portoes.sh --listar     a tabela crua, que é o que o portão do portão lê
#   scripts/portoes.sh --interpretador  só o cabeçalho: qual python, e o que falta nele
#   scripts/portoes.sh --em-serie   um portão de cada vez, na ordem da lista (a mesma corrida, sem a pressa)
#   scripts/portoes.sh --sem-memoria  roda todos, sem pular o que já passou sobre os mesmos bytes
#
# EM PARALELO E COM MEMÓRIA (06/10/2026, OS-PORTOES-RODAM-EM-PARALELO-E-LEMBRAM-O-VERDE-01). Medido na
# `integra/1-6`: 66 portões, 664 s somados, um por um, e a mesma árvore verde há cinco minutos rodava os 66
# de novo. Agora os portões `py`, `bash` e `bin` rodam em `nproc` − 2 vagas, os `pytest` em três (a vez do
# `vez-do-pytest.sh` quando ele existe), cada `pytest` com HOME, XDG_*, TMPDIR, D-Bus e Xvfb PRÓPRIOS:
# dois portões nunca dividem lar, bus nem display. A saída de cada um vai a um arquivo e sai impressa na
# ORDEM DA LISTA, como sempre saiu. O veredito é o mesmo da corrida em série (`--em-serie` é o mesmo motor
# com uma vaga). E um portão verde fica lembrado pelo hash do que ELE lê (`scripts/recibo_da_medida.py`,
# `chaves` e `anotar`): a corrida seguinte só o pula se esses bytes são idênticos; sem a quinta coluna da
# tabela, são os da árvore inteira. `--sem-memoria` e a variável `CI` desligam a memória, e o recibo do
# push continua pedindo a camada completa da MESMA árvore, com ou sem memória.
#
# O INTERPRETADOR SE DECLARA. A casa já pagou por medir contra a biblioteca
# errada — "todo instrumento tem de declarar qual biblioteca está usando" — e
# `gerar-tabela-de-curvas.py --check` quebra com `ModuleNotFoundError: pydantic`
# no `python3` pelado e passa no `.venv`. Aqui há UM python para todo portão de
# python, e ele sai impresso no cabeçalho da execução.
set -uo pipefail

RAIZ="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(dirname "$(readlink -f "$0")")")"

# ---------------------------------------------------------------------------
# A TABELA. Colunas: camada|id|runner|argumentos[|entradas]
#
#   camada   rapido   | completo  | suite
#   runner   py (o python resolvido) | bash | bin (binário do venv, senão PATH)
#
# A QUINTA COLUNA É OPCIONAL (06/10/2026), vem depois das quatro e quem lê só as quatro não se quebra. Ela
# declara o que o portão LÊ, para a memória do verde. Sem ela, vale o lado seguro: a árvore inteira.
#   um glob       `src/**`: só estes (o ignorado também), e glob que não casa nada faz o portão rodar sempre
#   @sempre       o portão lê a máquina ou a história do git, e nunca é lembrado
#   @dia          o portão compara com a data de hoje (prazo que vence): a data entra na chave
#   @head         o portão lê a história a partir do HEAD: o HEAD entra na chave
#
# Tempos medidos nesta árvore em 25/08/2026, `dev` em f475b2a, e é por eles que
# a camada rápida existe: `validar-acentuacao.py --all` sozinho custa 38 s e o
# `shellcheck` sobre o `install.sh` de 219 KB custa 11,4 s -- os dois juntos são
# oito vezes a camada rápida inteira, que fechava em 5,3 s com QUINZE portões.
# O tempo é de 25/08 e fica com a data dele; a CONTAGEM envelhece sozinha e por
# isso já virou número errado duas vezes — dizia 21 `rapido` e 7 `completo`
# enquanto a tabela tinha o dobro. Medida em 06/10/2026: **50 `rapido` e 19
# `completo`** (69 no `portoes.sh` sem argumento), mais 1 `suite`. Quem mexer
# aqui conta de novo, e o comando é o dono da resposta:
#   grep -cE '^rapido\|' scripts/portoes.sh ; grep -cE '^completo\|' scripts/portoes.sh
# ---------------------------------------------------------------------------
_LISTA() {
  cat <<'TABELA'
rapido|contrato-ipc|py|scripts/gerar-contrato-ipc.py --check
# 31/08/2026, decisão dela: este portão passou a cobrir também as planilhas de
# `docs/data/` — o mapa carregava 762 citações `arquivo:linha` e NENHUMA tinha
# portão. Nasce em zero (nenhuma aponta além do fim hoje), e continua na camada
# rápida porque o preço foi medido: 33 ms só `docs/protocol/`, 101 ms com o
# mapa, o caderno e as decisões dela juntos -- 903 citações conferidas.
rapido|citacoes-de-linha|py|scripts/validar-citacoes-de-linha.py --all
# E O `src/` NÃO ESTAVA COBERTO — 06/09/2026, achado da A-PALAVRA-MESA-SAI-01.
# O portão acima varre `docs/` e as planilhas: 2.977 citações em 21 documentos e
# 9 planilhas, verde. As citações escritas em COMENTÁRIO DE CÓDIGO ficavam de
# fora, e quem as conferia era um teste que a lista de portões não rodava —
# sete endereços mortos em `src/` atravessaram a leva inteira com os 44 verdes ao
# lado. *"Se dois portões da suíte medem coisa que a lista não roda, o piso tem
# furo"*, e tinha. Ele entra na camada COMPLETA porque custa ~60 s: ele abre
# cada arquivo citado e confere a âncora, não só o número de linhas.
completo|citacoes-no-codigo|pytest|tests/unit/test_portao_o_par_com_metade_ligada.py
# NADA-MOCKADO-01, 09/09/2026 — a pergunta dela virou portão: *"não tem nada
# rodando em sandbox ou mockada, certo?"*. Uma linha do mapa que diz `aciona=sim`
# está afirmando que o APARELHO faz aquilo; ele exige `provado_por` ou uma
# ressalva declarada, e trava a dívida onde ela está (36 sem nenhum dos dois, de
# 104 sem prova). Camada RÁPIDA: lê um CSV, custa milissegundos.
rapido|nada-mockado|pytest|tests/unit/test_portao_nada_e_afirmado_sem_prova.py
# A RÉGUA DE PRONTO DELA — CABO-BT-PERFIL-CONTROLE-01, 09/09/2026. A palavra
# dela de 08/09: "tudo funcionando por cabo ou bt ou tudo funcionando via perfil
# e dentro de cada um um setting pra cada controle". Virou régua: toda feature
# que a TELA oferece responde as quatro perguntas, e a lista de features é LIDA
# dos `data-gesto` das dez páginas — nunca digitada. Camada RÁPIDA: lê dez HTML,
# um CSV e o fonte do `schema.py`, custa milissegundos.
rapido|quatro-respostas|py|scripts/check_cabo_bt_perfil_controle.py
rapido|quatro-respostas-morde|pytest|tests/unit/test_portao_a_regua_das_quatro_respostas.py
# A QUINTA PERGUNTA — TUDO-FUNCIONA-01, 09/09/2026. A cobrança dela: "pq o
# programa de dias a fio é de brinquedo? uma prova de conceito?". As quatro
# acima leem `*_aciona` ("o Hefesto MEXE nisso?"); esta lê `*_ate_onde_foi`
# ("até onde a PROVA chegou?"), e a diferença é o critério do primeiro degrau:
# *tratar MONTOU como «funciona» é a mentira mais cara desta casa*. Como a tela
# não confessa dívida nossa (ordem dela de 07/09), a falta mora aqui — com
# CUSTO e com DONA, e os custos NUNCA somados numa frase só. Camada RÁPIDA:
# 76 ms, e reaproveita as duas réguas donas (a lista de features e a escada).
rapido|ate-onde-a-prova-chegou|py|scripts/check_ate_onde_a_prova_chegou.py
rapido|ate-onde-a-prova-chegou-morde|pytest|tests/unit/test_portao_a_quinta_pergunta_morde.py
rapido|mapa-de-canais|py|scripts/gerar-mapa.py --check
rapido|fatos-de-tela|py|scripts/gerar-fatos-de-tela.py --check
rapido|fala-de-tela|py|scripts/validar-fala-de-tela.py --all|@dia
rapido|caducos|py|scripts/validar-caducos.py --all
# O TEXTO PÚBLICO FALA COM QUEM USA — 28/09/2026: README, docs/usage, .github
# (menos workflows), NOTICE, CHANGELOG e o metainfo, sem ID, sem «dela» e sem o
# vocabulário de quem constrói. Os falsos positivos se declaram no script.
rapido|texto-publico|py|scripts/check_texto_publico.py
rapido|palavra-de-tela|py|scripts/validar-palavra-de-tela.py --all
rapido|version-consistency|py|scripts/check_version_consistency.py
rapido|curvas|py|scripts/gerar-tabela-de-curvas.py --check
rapido|paridade-transporte|py|scripts/check_paridade_transporte.py|@dia
# 03/09/2026: O TERCEIRO NÚMERO. Os dois outros medem a interface nova contra
# ela mesma (campos escritos; publicado × mockup) e nenhum responde "o que a GTK
# faz e o HTML não faz" -- que é de onde sai a fila. Este confere as 396
# features de `docs/data/paridade-gtk-html.csv` contra o CÓDIGO, e a metade que
# importa é a regra `divida-fechada`: quando alguém FECHAR uma dívida, ele
# reprova para o dado ser atualizado. Sem isso o número vira propaganda no dia
# seguinte à primeira cura. Camada rápida porque custa 0,4 s.
rapido|paridade-gtk-html|py|scripts/check_paridade_gtk_html.py
# O DONO DE CADA COMPORTAMENTO — 05/09/2026, e a queixa é dela: *"estamos
# recriando um produto que estava praticamente pronto pro gtk"*. Cinco laudos
# mediram 410 comportamentos das dez abas; os 50 que decidem estão em
# `docs/data/donos-de-comportamento.csv` com o endereço do dono. O portão não
# julga se um código recria — ele impede o LAUDO de envelhecer: endereço morto,
# cura descosturada, SO-GTK que já migrou, e a dívida declarada, que só desce.
rapido|donos-de-comportamento|py|scripts/check_donos_de_comportamento.py
# A CATRACA DA ORIGEM — 03/10/2026, a ordem dela de 02/10: *«a cada script novo,
# cada alteração nova enxugariamos e deixariamos o projeto mais enxuto, porém cada
# vez mais inteligente e preciso»*. Três números que só descem (caso especial fora
# do dono do eixo, remendo de sintoma por arquivo, linhas do projeto) sobre o
# motor `scripts/catraca.py`; o tamanho que cresce exige `Origem: <id>` na faixa.
# É portão e não gancho de commit porque o cherry-pick não roda gancho. A mordida
# é `tests/unit/test_a_catraca_da_origem_morde.py`, na suíte.
rapido|a-origem|py|scripts/check_a_origem.py|@sempre
# A DECISÃO TEM PROVA — 06/10/2026, DECISAO-SEM-DONO-01. O registro das decisões dela guardava a
# palavra e parava ali: a decisão de 25/08 sobre o microfone esperou 23 dias e três pedidos. O
# campo `prova` liga a linha a uma função de teste que cita o id; decisão nova sem prova (ou sem
# a marca `processo`) reprova nomeada, e o piso desce pelo `--aceitar` e só sobe à mão, no diff.
# O portão mede que a prova EXISTE, não que ela morde: a mordida é de quem sobe a decisão a
# `implementada`.
rapido|decisao-tem-prova|py|scripts/check_a_decisao_tem_prova.py|docs/data/decisoes-de-produto.csv docs/data/decisoes-sem-prova.txt tests/**
# BROADCAST PROIBIDO — 06/10/2026, OS-PORTOES-QUE-NINGUEM-CHAMA-01. Nasceu em 25/08, verde, e ficou 42 dias
# sem chamador: nesse tempo entrou uma rota de saída que escrevia em todo controle conectado sem perguntar
# o seletor (o brilho das luzes de número). Reprova função de `src/` com fan-out sem escopo, nomeando-a.
rapido|broadcast-proibido|py|scripts/check_broadcast_proibido.py|src/**
# NADA NOVO APONTA PARA A JANELA — 06/09/2026, sprint GTK-1. Decisão dela
# (D-0609-GTK-LEVA-INTEIRA): *"a ideia sempre foi reaproveitar o que fiz no gtk e
# não apontar nada mais pra lá mas pro html"*. A janela GTK sai em três sprints
# (GTK-1 inventário, GTK-2 os leitores do glade, GTK-3 a remoção); enquanto ela
# sai, a lista de quem ainda aponta para lá SÓ DIMINUI — senão a GTK-3 persegue
# um alvo que cresce.
# O inventário é `docs/data/o-que-ainda-aponta-para-a-janela.csv`: 255 pares
# (arquivo, alvo) e 522 citações, cada uma com veredito. O portão tem DUAS
# metades: citação nova reprova nomeando arquivo e linha; linha nova no CSV sem
# veredito reprova. Ele NÃO é um `grep`: a natureza de cada citação sai do
# `tokenize`, porque 111 das 255 são PROSA e um grep as contaria como dependência.
# CAMADA `completo`, e o número é a razão: 3,7 s medidos em 06/09/2026, contra
# ~5 s da camada rápida INTEIRA. Ele lê 1.694 arquivos. O `bash scripts/portoes.sh`
# sem argumento — que é o que esta casa manda rodar antes de fechar leva — o
# alcança; o `--rapido`, que roda a cada salvamento, não paga por ele.
completo|nada-aponta-para-a-janela|py|scripts/check_nada_aponta_para_a_janela.py
rapido|test-data|bash|scripts/check_test_data.sh
rapido|endereco-de-radio|py|scripts/check_endereco_de_radio.py
rapido|endereco-dela-em-toda-forma|py|scripts/check_o_endereco_em_toda_forma.py|@sempre
# O IRMÃO DO DE CIMA, PARA O SERIAL — 03/09/2026, e o pedido é dela: *"sim, faz
# o portão pro número de série"*. O serial de fábrica identifica a unidade dela
# tão bem quanto o MAC, e a regra desta casa é sobre ARQUIVO VERSIONADO, não
# sobre a palavra "MAC".
# NÃO É A PRIMEIRA RÉGUA DE SERIAL, e isso foi medido escrevendo esta: o
# `test_nenhum_serial_de_fabrica_real_no_repo`, dentro do `mac-por-oui`, existe
# desde 15/08 e acusou o forjado que este portão acabara de criar. Ele é o
# AUTORITATIVO — pega a forma exata de um DualSense em texto, em hexdump e em
# corrida hexadecimal colada.
# O QUE ESTA ACRESCENTA são duas coisas: a CAMADA (1,2 s contra 12 s, logo roda
# antes do commit em vez de no fim da suíte) e a LARGURA (15 a 20 caracteres,
# que alcança serial de 8BitDo e de Pro Controller, não só de DualSense).
# A camada é a lição de HOJE: o `mac-por-oui` acusava os 37 endereços crus da
# manhã, mas era teste da SUÍTE, e a suíte roda no FIM.
rapido|serial-de-aparelho|py|scripts/check_numero_de_serie.py
rapido|faixa-sintetica|py|scripts/check_faixa_sintetica.py
# 03/09/2026 — O PORTÃO AUTORITATIVO DE MAC ENTRA AQUI, e a razão é medida: os
# documentos da leva de cliques trouxeram 37 endereços CRUS da bancada, e este
# teste os acusou — a lista dele já trazia os quatro OUIs. Ele não estava cego;
# ele só não era rodado. Era teste da SUÍTE, e a suíte roda no FIM: entre o
# commit que vazou e a reprovação havia um dia inteiro de trabalho.
# Camada `completo` porque custa ~12 s — varre toda a árvore versionada, e
# dentro dos `.gz` também.
completo|mac-por-oui|pytest|tests/unit/test_docs_mac_anonimato.py
# A TERCEIRA RÉGUA, e ela mede o que as outras duas não podem: fixture de teste
# tem de usar faixa FORJADA (`aa:bb:cc`), não endereço real podado — a máscara
# da casa preserva o OUI, e o OUI é identidade de fabricante do aparelho dela.
completo|mac-de-fixture|pytest|tests/unit/test_anonimato_de_fixtures.py
# O `saida-de-agente` SAIU EM 15/09/2026, junto com o seu insumo. A régua
# varria `docs/process/agentes/` atrás de glifo que o sanitizador da casa troca
# por texto; a pasta inteira deixou de ser versionada por ordem dela, e régua
# sem insumo dá verde sobre o vazio — que é pior que portão nenhum.
# O QUE COBRIA O MESMO RISCO E FICA: o `glifos` (`validar-glifos.py`, critério
# Emoji_Presentation) sobre a árvore versionada, e o gancho de pre-commit, que
# usa faixas largas. O que se perdeu foi só o alcance sobre arquivo que não
# está mais aqui.
# A AUTORIA — uma régua só, `scripts/check_autoria.py`, a mesma do gancho de
# pre-push e do workflow `autoria` do CI. Quem pode assinar é o `.mailmap` (autor,
# committer e tagger, nome e endereço), e os termos que não se publicam vêm de uma
# lista fora do repositório (`git config autoria.vedados`): sem ela a régua sai
# «NÃO MEDIDO» e reprova, em vez de dar verde. Mede a história que VIAJA, toda vez
# que alguém roda os portões, porque o gancho de commit-msg não roda em
# cherry-pick, rebase, merge --no-edit nem sob --no-verify, e esta casa integra
# leva por cherry-pick. O `.mailmap` nasceu da palavra dela de 15/09/2026:
# *"o emaillist lá deveria ser o meu e o do andre apenas."*
rapido|autoria-historia|py|scripts/check_autoria.py historia|@sempre
completo|casa-sabe|pytest|tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py
# 25/08/2026: o portão que exige que TODO portão tenha quem o rode não era
# rodado por esta lista — só pela camada `suite`, que é de quem coordena e
# roda no fim. Achado pela conferência da frente C2, e a ironia é o ponto.
completo|portao-tem-chamador|pytest|tests/unit/test_portao_todo_portao_tem_chamador.py
# 04/09/2026 — O PORTÃO QUE MEDE O PRÓPRIO INSTRUMENTO. Numa árvore de voo o
# cabeçalho deste script imprimia a venv da `-estavel`, outra cópia do
# repositório, sem structlog/playwright/ruff/mypy: QUATRO vermelhos falsos sobre
# código são. A causa era a regra da POSIÇÃO (`worktree list | awk NR==1`), e a
# regra passou a ser a de CAPACIDADE. Ele entra na camada `completo` e não na
# suíte pela lição que este arquivo já carrega no `mac-por-oui`: era teste da
# SUÍTE, e a suíte roda no FIM -- entre o vazamento e a reprovação havia um dia
# inteiro de trabalho. Custa ~1 s.
completo|interpretador-do-portao|pytest|tests/unit/test_o_portao_declara_o_interpretador.py|@sempre
completo|a-tela-dela|pytest|tests/unit/test_a_tela_nao_recebe_janela_de_teste.py
completo|o-instrumento-e-a-tela|pytest|tests/unit/test_o_instrumento_nao_abre_na_tela_do_usuario.py
completo|a-frase-banida|pytest|tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py
completo|src-desta-arvore|pytest|tests/unit/test_a_suite_mede_esta_arvore.py|@sempre
completo|o-piloto-e-a-arvore|pytest|tests/unit/test_o_piloto_aponta_para_a_propria_arvore.py
rapido|desenho-aprovado|py|scripts/check_o_desenho_aprovado.py
# 07/09/2026 — ELA MEDIU O DEFEITO NA MESA: *"4 controles conectados mas as
# infos dos dos outros 2 ultimos não aparecem (…) isso em todas as abas."* O  # noqa-acento: citação literal
# dado chegava inteiro; o que faltava era ONDE POUSAR — o ramo do lugar vazio
# emitia cartão sem um único `data-campo`, e o piloto procura o endereço DENTRO
# do bloco `[data-controle="pN"]`. Sete das dez abas tinham o mesmo defeito, e
# é por isso que a régua é UMA e atravessa as dez: cada `abaNN.py` ganhou a
# sua, mas nenhuma delas vê uma aba NOVA nascendo com o ramo separado.
rapido|os-quatro-lugares|py|scripts/check_os_quatro_lugares.py
# 07/09/2026 — O IRMÃO DO DE CIMA, PELO OUTRO LADO. Aquele cobra que os quatro
# lugares tenham os mesmos ENDEREÇOS; este cobra que o lugar sem aparelho não
# OFEREÇA gesto nenhum, que é a decisão dela de 31/08/2026. Os dois são
# necessários e nenhum vê o buraco do outro: a 01-jogar tinha os doze endereços
# certos E três chips clicáveis em cada uma das duas colunas sem controle.
# POR QUE A REDE DA CASA NÃO BASTAVA: a S-04 da folha (`monta.py:544`) mira
# `button, input, select, textarea, [contenteditable]`, e o chip de máscara da
# 01 é um `<span>` — nenhum dos cinco.
# ELE É `pytest` E NÃO UM SCRIPT DE `scripts/`, e a razão é o motor: a régua
# abre a página no Chrome headless e pergunta ao MOTOR quem recebe o clique
# (`elementFromPoint`). Custa 1,8 s, e por isso fica na camada rápida.
# A auto-checagem da própria `aba01.py` NÃO substitui esta: ela só roda com
# `python aba01.py`, e uma régua que espera alguém a chamar não protege
# ninguém — foi o que a conferência de 07/09 derrubou na aba 04.
rapido|gesto-em-lugar-vazio|pytest|tests/unit/test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio.py
# O IRMÃO DA 04, e ele nasceu do MESMO conferente, no mesmo dia — 07/09/2026.
# Se o de cima pegou o gesto que SOBRAVA num lugar vazio, este pega o que
# FALTA num lugar cheio: a conferência escondeu `Automático` e `Desligar` das
# duas colunas CONECTADAS com uma linha de CSS e a suíte inteira não mudou —
# 13 falhas antes, 13 depois, lista idêntica. A cobertura desta aba só existia
# na direção "escondido no vazio", e esconder DEMAIS satisfaz essa metade.
# ELE MEDE OS DOIS SENTIDOS, no Chrome, com `elementFromPoint`: nada oferecido
# no vazio, TUDO oferecido no cheio, e os dois passos do piloto (`1b`/`1c`) que
# viram a marca sem recarregar. Custa 2,1 s.
# A §4 DA `aba04._conferir` NÃO SUBSTITUI ESTE: ela só roda com
# `python aba04.py`, e foi exatamente essa a folga que a conferência mostrou.
rapido|gesto-onde-deve-04|pytest|tests/unit/test_a_04_iluminacao_o_gesto_esta_onde_deve.py
rapido|identidade-de-cima|py|scripts/check_identidade_vem_de_cima.py
# 03/09/2026, a lei dela: *"cada pessoa tem um dualsense diferente (…) nada
# hardcoded, trazer tudo que eu já mapeei"*. O irmão acima acha cor congelada
# em elemento SEM endereço; este acha cor de aparelho cravada mesmo ONDE o
# endereço existe -- porque um endereço com o alvo errado não alcança a cor.
# NASCE VERMELHO, e é o ponto: 360 cravados em sete das dez abas, o número de
# onde as ondas partem. Ele distingue a TABELA dela (a folha com os 28 modelos,
# que é o mecanismo certo) da ESCOLHA cravada (a folha podada para um só).
# VERMELHO POR DECISÃO DELA, e não por descuido — 03/09/2026. Ele mede a página
# PUBLICADA, e a bancada já está em ZERO: `--bancada` devolve 0 plástico, 0
# colorway, 0 zona nas dez abas (era 503 na manhã deste dia). Os 358 que sobram
# vivem só no publicado, e publicar é ATO DELA.
#
# ELA ESCOLHEU PUBLICAR POR ÚLTIMO, depois do install e dos cliques: *"deixa
# para o fim, depois do install"*. Até lá este portão fica vermelho, e ficar
# vermelho é o comportamento CERTO — ele está dizendo a verdade sobre a tela
# que ela vê hoje.
#
# NÃO O CALE, e não publique para o silenciar. `--publicar` é a palavra dela, e
# antecipá-lo entregaria dez abas que ela ainda não olhou.
rapido|cor-vem-do-aparelho|py|scripts/check_a_cor_vem_do_aparelho.py
# O `colisao-de-sprints` (15/09/2026) e o `sprints-fechadas` (02/10/2026,
# A-CASA-SEM-METALINGUAGEM-01) saíram pela mesma razão: liam `docs/process/`,
# o caderno de quem coordena, que não viaja pelo git. Os dois moram nas
# ferramentas de quem coordena, fora do repositório.
rapido|icones|bash|scripts/gerar_icones.sh --check
rapido|packaging-parity|bash|scripts/check_packaging_parity.sh
rapido|glifos|py|scripts/validar-glifos.py --all
rapido|pecas-do-dualsense|py|scripts/check_pecas_do_dualsense.py
# 27/08/2026: o irmão acima confere que o NOME da peça bate com o LUGAR dela;
# este confere que a COR bate com o dado. Antes dele, nenhuma régua sabia dizer
# se o hex do desenho estava certo, porque não havia com o que comparar — o
# Cosmic Red era #b11f54 e a amostragem devolveu #A51C48. 3,5 s.
rapido|cores-do-dualsense|py|scripts/check_cores_do_dualsense.py
# 20/09/2026: o terceiro que abre o Chrome, e a pergunta dele é a CAIXA. Os dois
# de cima medem o desenho do controle; este mede se o cartão da aba 02 ainda
# cabe no orçamento que `aba02.PARA_O_CARD` declara, e se algum rótulo dele sai
# cortado. Nasceu com o empilhamento da fileira da saída de som — sem trava, a
# próxima altura a crescer apareceria na tela dela, não aqui. ~4 s.
rapido|altura-do-cartao|py|scripts/check_a_altura_do_cartao.py
rapido|regua-de-tela|py|scripts/check_regua_de_tela.py|@sempre
# A ORDEM DELA, 07/09/2026: *"o layout não informa os nossos defeitos."* Este
# portão lê as dez páginas dos DOIS lados (bancada e publicado) e todo `Fala`
# de `src/`, e obriga a DECLARAR toda frase com forma de confissão: de quem é o
# sujeito, e desde quando. Ele não decide sozinho de propósito — nenhuma
# expressão regular separa *"o jogo ainda não recebeu"* de *"o Hefesto ainda não
# faz"*, e as duas estavam na tela no dia em que ele nasceu.
rapido|tela-nao-confessa|py|scripts/check_a_tela_nao_confessa.py
# A MOLDURA — 08/09/2026, e ele nasceu de um buraco entre as duas réguas acima.
# Elas medem o CORPO das dez páginas; a barra de título é GTK, o `.desktop` é
# INI e a unit é systemd. *A régua parava na borda da `<body>`, e a tela dela
# não para.* Ela leu "Hefesto / as dez abas, vivas" na barra do produto
# instalado, e na PRIMEIRA corrida esta régua achou a segunda ocorrência que
# ninguém tinha visto: a mesma frase na dica do `.desktop`, que a dock mostra
# antes de a janela existir. Quatro peneiras, e duas são LIDAS de quem já as
# possui — a forma de confissão do irmão acima e as palavras banidas do
# `frases_que_ela_baniu`.
rapido|janela-nao-confessa|py|scripts/check_a_janela_nao_confessa.py
# A CAIXA ALTA QUE NÃO SIGNIFICA NADA — 11/09/2026, ordem dela: *"Esse tipo de
# coisa não pode se repetir na interface."* Ela leu na MESMA tela `CABO` na fita
# e `cabo` no cartão logo abaixo. O `CABO` não estava escrito em lugar nenhum:
# o HTML dizia `cabo` e quem gritava era UMA LINHA DE FOLHA DE ESTILO — por isso
# a régua tem duas peneiras, e uma sozinha daria verde sobre o defeito da outra.
# A dívida das dez páginas sai declarada com o dono, e não reprova; o que
# reprova é a caixa alta NOVA.
rapido|maiuscula-decorativa|py|scripts/check_a_maiuscula_decorativa.py
rapido|maiuscula-decorativa-morde|pytest|tests/unit/test_portao_a_maiuscula_decorativa_morde.py
# A GRAFIA DO NOME — 11/09/2026, `F6-O-NOME-TEM-UM-DONO`. O produto se chama
# `DualSense4Unix`, com o `S` do DualSense, e `utils/identidade.py` escrevia o
# `S` em minúscula — 427 linhas de 174 arquivos. A grafia errada TRAVAVA uma
# cura já medida: a barra da janela nasceu com o nome DIGITADO porque ler do
# dono poria a grafia errada na tela dela. Duas peneiras, e uma sozinha daria
# verde sobre o defeito da outra — a grafia, e o DONO (a moldura digitando o
# nome reprova mesmo com a grafia certa). Identificador técnico não se troca:
# `wm_class`, app-id do Flatpak e os três nós uinput ficam com a grafia velha,
# cada um com a razão medida na docstring. Cura idempotente para a costura:
# `scripts/aplicar_a_grafia_do_nome.sh`.
rapido|grafia-do-nome|py|scripts/check_a_grafia_do_nome.py
rapido|grafia-do-nome-morde|pytest|tests/unit/test_portao_a_grafia_do_nome_morde.py
# A CATRACA DA TRADUÇÃO — TRADUZIR-O-PROJETO-01, 20/09/2026, e a ordem é dela:
# *"Um Hook que vá facilitando isso seria maravilhoso. Pois organicamente   # noqa-acento: citação literal
# deixaríamos fácil pra gente e pro outro"*.  # noqa-acento: citação literal
# Ele não traduz nada e não pede mutirão: impede TRÊS números de subirem, e
# cobra só de quem escreve a linha nova. (1) arquivo que nenhuma regra de
# `docs/data/zonas-de-lingua.toml` alcança, piso ZERO; (2) unidade de texto de
# tela sem endereço de tradução, hoje PENDENTE -- não existe forma de endereço
# neste projeto, e um contador nessas condições devolveria zero, que se lê como
# verde; (3) bytes de comentário dentro das dez páginas publicadas, medidos com
# parser e não com regex.
# PENDENTE NÃO É VERDE, e o portão diz isso em voz alta: a medida da tela acorda
# sozinha no dia em que a I18N-DA-TELA-NOVA-01 definir a forma do endereço, e
# reprova pedindo o piso novo -- instrumento que sabe do próprio risco RESOLVE.
# Camada RÁPIDA: 643 ms medidos nesta árvore, lendo as dez páginas, a tabela de
# zonas, os 2.471 caminhos versionados e o AST de `app/actions/`.
rapido|projeto-traduzivel|py|scripts/check_o_projeto_e_traduzivel.py
rapido|projeto-traduzivel-morde|pytest|tests/unit/test_o_projeto_e_traduzivel_morde.py
# OS PORTÕES DE PÁGINA NÃO DEPENDEM DA REDE — 06/10/2026, costura da irmã
# (OS-PORTOES-LENTOS-FICAM-RAPIDOS-POR-DENTRO-01): a régua que prova que os portões que abrem uma página
# a abrem pelo `scripts/chrome_sem_rede.py`, sem esperar fonte nem script de fora. A irmã a deixou fora
# desta lista porque o `portoes.sh` não era posse dela. Camada RÁPIDA: ~20 s, e é ela que segura a cura.
rapido|portoes-lentos-rapidos|pytest|tests/unit/test_os_portoes_lentos_ficam_rapidos.py
rapido|ruff|bin|ruff check src/ tests/|src/** tests/** pyproject.toml .gitignore
completo|shellcheck|bin|shellcheck -S error scripts/*.sh scripts/ci/*.sh scripts/banco_de_prova/*.sh install.sh uninstall.sh|scripts/*.sh scripts/ci/*.sh scripts/banco_de_prova/*.sh install.sh uninstall.sh
completo|referencias-docs|py|scripts/validar-referencias-docs.py --all
completo|anonimato|bash|scripts/check_anonymity.sh
completo|autoria-arvore|py|scripts/check_autoria.py arvore|@sempre
completo|acentuacao|py|scripts/validar-acentuacao.py --all
completo|mypy|bin|mypy src/hefesto_dualsense4unix|src/** pyproject.toml
completo|coleta-sem-gtk|py|scripts/check_a_coleta_sem_gtk.py
suite|suite|bin|pytest -q
TABELA
}

# ---------------------------------------------------------------------------
# AS DIVERGÊNCIAS DECLARADAS. O portão do portão exige que toda diferença entre
# esta tabela e o `ci.yml` esteja escrita aqui, com o motivo. Diferença
# declarada é decisão; diferença calada é a M9 de novo.
# ---------------------------------------------------------------------------
_DIVERGENCIAS() {
  cat <<'DIV'
FORA-DO-LOCAL|scripts/ci/instalar_como_usuaria.sh|ensaio de instalação em máquina descartável; rodar na máquina dela mexeria no sistema vivo.
FORA-DO-LOCAL|scripts/banco_de_prova/sonda.sh|06/10/2026, O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01 (parte 0): é a sonda do kernel do runner (carrega uhid e hid_playstation, cria um gadget USB e roda o install.sh com sudo), só em workflow_dispatch. Cria aparelho no kernel: na máquina dela mexeria no que ela usa.
FORA-DO-LOCAL|scripts/i18n_compile.sh|regenera os .mo, que são artefato compartilhado, e não tem forma --check. Portão que reescreve artefato não roda na árvore de agente.
FORA-DO-CI|scripts/check_o_endereco_em_toda_forma.py|27/09/2026, O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01: pergunta à máquina dela os endereços reais (maquina.json do HOME de verdade, bluetoothctl e sysfs) e procura os octetos 4 e 5 em toda forma; no runner não há endereço nenhum a perguntar, e o portão só diria NÃO MEDIDO (O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01, 27/09).
FORA-DO-LOCAL|pre-commit|DECISÃO EM ABERTO, e não é minha: ou o framework entra no install.sh sem flag, ou os dez portões do .pre-commit-config.yaml migram para o gancho e o .yaml some (INFRA-DE-EXECUCAO-01, I14 e §9.4). Enquanto não decidido, o CI é o único que o roda -- e esta linha declara isso em vez de fingir que não existe. Medido: `which pre-commit` -> not found nesta máquina.
FORA-DO-LOCAL|scripts/rodar-a-suite.sh|27/09/2026: é a suíte inteira, e em casa ela roda no fecho, por quem coordena e com a máquina livre, depois dos portões (a lista «Antes de fechar qualquer leva»): toca nós uinput de verdade e leva quarenta minutos. No CI é o job gtk-real, com o GTK real.
DIV
}

_uso() { sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \?//'; }

CAMADAS="rapido completo"
MODO=""
EM_SERIE=0
SEM_MEMORIA=0
for _opcao in "$@"; do
  case "$_opcao" in
    --listar)
      _LISTA | sed 's/^/PORTAO|/'
      _DIVERGENCIAS
      exit 0 ;;
    --rapido)  CAMADAS="rapido" ;;
    --interpretador) CAMADAS=""; MODO="interpretador" ;;   # só o cabeçalho; ver o bloco do interpretador
    --suite)   CAMADAS="rapido completo suite" ;;
    --aceite)  CAMADAS="rapido completo suite" ;;
    --em-serie) EM_SERIE=1 ;;
    --sem-memoria) SEM_MEMORIA=1 ;;
    -h|--help) _uso; exit 0 ;;
    *) echo "ERRO: opção desconhecida '${_opcao}'. Veja $0 --help" >&2; exit 2 ;;
  esac
done

# --- o interpretador, resolvido e DECLARADO -------------------------------
#
# O DEFEITO QUE ESTE BLOCO CUROU, medido em 04/09/2026 dentro de uma árvore de
# voo: o cabeçalho imprimia
#
#     python  /mnt/.../hefesto-dualsense4unix-estavel/venv/bin/python
#
# — a venv de OUTRA CÓPIA do repositório, sem playwright, sem structlog e sem
# ruff, e por isso com QUATRO vermelhos falsos. A causa era uma suposição
# escrita aqui: `worktree list | awk NR==1` devolve a árvore PRINCIPAL do
# `.git`, e esta casa tem TRÊS árvores — a principal do git é a `-estavel`, que
# não é a de trabalho. "A primeira da lista" nunca foi "a que tem as
# dependências".
#
# É a família de defeito que esta casa persegue acima de todas: **o instrumento
# apontando para outra coisa.** Um portão que roda com o interpretador errado
# não é um portão vermelho — é um portão que não mede.
#
# A REGRA NOVA: não se adivinha a venv pela POSIÇÃO na lista. PERGUNTA-SE a ela
# se tem o que os portões precisam, e a que responder sim ganha. Se nenhuma
# responder, o cabeçalho DIZ, em vez de deixar o vermelho falso explicar-se
# sozinho.
_VENV_FALTA=""

_venv_completa() {  # rc=0 se esta venv tem o que os portões precisam
  local d="$1" falta=""
  "$d/python" -c 'import structlog, playwright' >/dev/null 2>&1 || falta="python:structlog/playwright"
  [ -x "$d/ruff" ] || falta="${falta:+$falta }bin:ruff"
  [ -x "$d/mypy" ] || falta="${falta:+$falta }bin:mypy"
  _VENV_FALTA="$falta"
  [ -z "$falta" ]
}

_venv_bin() {
  local d cand=() primeira="" w
  # 1. a venv DESTA árvore, se houver.
  cand+=("$RAIZ/.venv/bin" "$RAIZ/venv/bin")
  # 2. as das outras árvores do mesmo `.git` — TODAS, não só a primeira. Numa
  #    árvore de agente não há venv (o worktree copia só o que o git rastreia,
  #    e `.venv/` é ignorado), então é aqui que ela é achada.
  while read -r w; do
    [ -n "$w" ] && cand+=("$w/.venv/bin" "$w/venv/bin")
  done < <(git -C "$RAIZ" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')

  for d in "${cand[@]}"; do
    [ -x "$d/python" ] || continue
    [ -n "$primeira" ] || primeira="$d"
    if _venv_completa "$d"; then echo "$d"; return 0; fi
  done
  # Nenhuma completa: devolve a primeira que existe, e o chamador AVISA.
  if [ -n "$primeira" ]; then
    _venv_completa "$primeira" || true   # repovoa _VENV_FALTA com a escolhida
    echo "$primeira"; return 0
  fi
  return 1
}

VENV_BIN="$(_venv_bin || true)"
if [ -n "${HEFESTO_PY:-}" ]; then
  PY="$HEFESTO_PY"
elif [ -n "$VENV_BIN" ]; then
  PY="$VENV_BIN/python"
else
  PY="$(command -v python3)"
fi

# A CONFERÊNCIA É SOBRE O INTERPRETADOR QUE VAI RODAR, não sobre o que foi
# escolhido — senão um `HEFESTO_PY` apontado para uma venv capenga passa em
# silêncio, que é o mesmo defeito com outra porta. Medido ao morder o próprio
# conserto, em 04/09/2026.
VENV_INCOMPLETA=""
if ! _venv_completa "$(dirname "$PY")"; then
  VENV_INCOMPLETA="$_VENV_FALTA"
fi

_bin() {  # resolve um binário: venv primeiro, PATH depois
  local nome="$1"
  if [ -n "$VENV_BIN" ] && [ -x "$VENV_BIN/$nome" ]; then echo "$VENV_BIN/$nome"
  else command -v "$nome" || echo "$nome"; fi
}

echo "portões — árvore ${RAIZ}"
echo "         python  ${PY}"
echo "         camadas ${CAMADAS}"
# O `src/` DESTA árvore vai na frente do PYTHONPATH, sempre.
#
# Aqui havia só um AVISO ("PYTHONPATH (vazio) -- armadilha"), e aviso não é
# cura: ninguém lê o cabeçalho de um comando que termina verde. Medido em
# 04/09/2026 numa árvore de integração — doze lotes de suíte e uma leva de
# portões mediram o `src/` de OUTRA cópia do repositório, porque a venv tem o
# pacote em modo editável apontando para a árvore onde ela nasceu. Não dá erro:
# dá `ImportError` de símbolo novo, que se lê como "o agente não terminou".
#
# É a mesma família do defeito do interpretador, e a mesma resposta: o script
# RESOLVE em vez de pedir que alguém lembre.
if [ -d "${RAIZ}/src" ]; then
  case ":${PYTHONPATH:-}:" in
    *":${RAIZ}/src:"*) : ;;
    *) PYTHONPATH="${RAIZ}/src${PYTHONPATH:+:${PYTHONPATH}}" ;;
  esac
  export PYTHONPATH
fi
echo "         PYTHONPATH ${PYTHONPATH:-(vazio)}"
if [ -n "${VENV_INCOMPLETA:-}" ]; then
  echo "         INTERPRETADOR INCOMPLETO -- falta: ${VENV_INCOMPLETA}"
  echo "         O VERMELHO QUE VIER PODE SER DO INSTRUMENTO, NÃO DO CÓDIGO."
  echo "         Aponte o certo: HEFESTO_PY=<árvore>/.venv/bin/python bash scripts/portoes.sh"
fi
# `--interpretador` para AQUI, e é ele que torna a resolução OBSERVÁVEL — que é
# a metade que faltava quando o defeito de 04/09 viveu meses: o python errado
# saía impresso e ninguém tinha como afirmar, numa régua, que ele estava certo.
if [ "$MODO" = "interpretador" ]; then
  [ -z "${VENV_INCOMPLETA:-}" ]; exit $?
fi
echo

# --- O LAR DE MENTIRA DO RUNNER `pytest` -----------------------------------
#
# MEDIDO na máquina dela em 21/09/2026, com o daemon VIVO: `bash
# scripts/portoes.sh` sem argumento fez o portão `casa-sabe` (42 testes)
# ESCREVER no `~/.config/hefesto-dualsense4unix` real — `controller_masks.json`
# zerado (78 -> 27 B), o perfil do jogo regravado, e o autoswitch trocou o
# perfil ATIVO dela no meio da corrida, de «Marvel's Guardians of the Galaxy»
# para «Personalizado».
#
# O `CANARIO-FS-01` do `conftest.py` viu e fez `session.exitstatus = 1`: o
# portão saiu **VERMELHO com os 42 testes PASSANDO**. Vermelho de ambiente
# lê-se como regressão, e é a armadilha nomeada na §6.1 do ONDE PARAMOS de
# 21/09.
#
# POR QUE O `conftest.py` NÃO BASTA: ele desvia `HOME` e os quatro `XDG_*` por
# fixture, mas `Path.home()` avaliado no IMPORT de um módulo do produto escapa
# do monkeypatch — é exatamente o que o texto do canário manda procurar.
# Desviar no AMBIENTE, antes de o processo nascer, alcança os dois casos: nesta
# corrida, nenhum `Path.home()` — em import ou em chamada — encontra a casa
# dela.
#
# PROVADO NOS DOIS SENTIDOS, no mesmo dia: com o HOME real, `rc=1` e quatro
# arquivos dela mudados; com o lar de mentira, `rc=0` e a casa dela intacta.
#
# O escopo é o runner `pytest` de propósito: é o único que carrega o produto
# inteiro. Os outros runners leem arquivo e não instanciam o daemon.
LAR_DE_MENTIRA="$(mktemp -d "${TMPDIR:-/tmp}/portoes-lar-XXXXXX")"
mkdir -p "$LAR_DE_MENTIRA"/{config,data,cache,state,runtime}
chmod 700 "$LAR_DE_MENTIRA/runtime"
trap 'rm -rf "$LAR_DE_MENTIRA"' EXIT
_AMBIENTE_DE_MENTIRA=(
  "HOME=$LAR_DE_MENTIRA"
  "XDG_CONFIG_HOME=$LAR_DE_MENTIRA/config"
  "XDG_DATA_HOME=$LAR_DE_MENTIRA/data"
  "XDG_CACHE_HOME=$LAR_DE_MENTIRA/cache"
  "XDG_STATE_HOME=$LAR_DE_MENTIRA/state"
  "XDG_RUNTIME_DIR=$LAR_DE_MENTIRA/runtime"
)

# --- O RECIBO DA MEDIDA -----------------------------------------------------
#
# A trava do push da máquina só deixa o `dev` subir com o recibo da camada
# completa da MESMA árvore (`<git comum>/hefesto-recibos/<árvore>.portoes-completo`).
# Em 26 e 27/09/2026 o `dev` subiu dez vezes com o CI vermelho: os portões só
# travavam se alguém os rodasse. Quem escreve o recibo é
# `scripts/recibo_da_medida.py`: `abrir` aqui, antes do primeiro portão, e
# `fechar` em `_sair`, com o rc que este script decide. Só quando a camada
# `completo` roda: o `--rapido` NUNCA deixa recibo. O recibo não muda o rc.
RECIBO_DA_CORRIDA=""
case " $CAMADAS " in
  *" completo "*)
    RECIBO_DA_CORRIDA="$(mktemp "${TMPDIR:-/tmp}/portoes-recibo-XXXXXX")"
    trap 'rm -rf "$LAR_DE_MENTIRA" "$RECIBO_DA_CORRIDA"' EXIT
    "$PY" "$RAIZ/scripts/recibo_da_medida.py" abrir portoes-completo \
      --raiz "$RAIZ" --corrida "$RECIBO_DA_CORRIDA" || true
    echo ;;
esac

# O fim de toda corrida que chega ao veredito: fecha o recibo e sai com o rc.
_sair() {
  local rc="$1" id bandeiras=()
  if [ -n "$RECIBO_DA_CORRIDA" ]; then
    for id in ${NAO_MEDIDOS[@]+"${NAO_MEDIDOS[@]}"} ${PULADOS[@]+"${PULADOS[@]}"}; do
      bandeiras+=(--nao-medido "$id")
    done
    # o que veio da memória fica dito no recibo: verde de OUTRA corrida sobre os mesmos bytes
    for id in ${LEMBRADOS[@]+"${LEMBRADOS[@]}"}; do
      bandeiras+=(--lembrado "$id")
    done
    echo
    "$PY" "$RAIZ/scripts/recibo_da_medida.py" fechar portoes-completo "$rc" \
      --raiz "$RAIZ" --corrida "$RECIBO_DA_CORRIDA" \
      --contagem "$((TOTAL - ${#NAO_MEDIDOS[@]})) de ${TOTAL} portões verdes" \
      ${bandeiras[@]+"${bandeiras[@]}"} || true
  fi
  exit "$rc"
}

# --- a corrida -------------------------------------------------------------
#
# A CORRIDA EM TRÊS TEMPOS (06/10/2026, OS-PORTOES-RODAM-EM-PARALELO-E-LEMBRAM-O-VERDE-01):
#
#   1. LER a tabela e escolher os portões da camada (o ausente da árvore sai nomeado, sem rodar);
#   2. LEMBRAR: perguntar ao `recibo_da_medida.py chaves` o hash do que cada portão lê, e pular quem já
#      passou sobre os mesmos bytes;
#   3. RODAR o resto em duas filas, cada uma com as suas vagas (a geral e a do `pytest`), com a saída de
#      cada portão num arquivo, e IMPRIMIR na ordem da lista, de modo que o relato lê igual ao da corrida
#      em série. O veredito, o `NÃO MEDIDO` e o recibo são os de sempre.
#
# O QUE NUNCA DIVIDE ESTADO: cada `pytest` leva o lar de mentira PRÓPRIO (`$LAR_DE_MENTIRA/<n>`), o D-Bus
# e o Xvfb próprios, e `-p no:cacheprovider` (dois pytest nunca escrevem o mesmo `.pytest_cache`).
VERMELHOS=()
AUSENTES=()
NAO_MEDIDOS=()
PULADOS=()
LEMBRADOS=()
VERDES_TSV=""
TOTAL=0
G_ID=(); G_RUN=(); G_ARGV=(); G_ENT=(); G_ESTADO=(); G_CHAVE=(); G_DICA=()

while IFS='|' read -r camada id runner argv entradas; do
  [ -z "${camada:-}" ] && continue
  case "$camada" in "#"*) continue ;; esac
  case " $CAMADAS " in *" $camada "*) ;; *) continue ;; esac
  estado="rodar"

  # PORTÃO DECLARADO E AUSENTE SAI VERMELHO NOMEANDO. Um script que sumiu da
  # árvore e some da corrida em silêncio é o portão cego da cicatriz acima.
  primeiro="${argv%% *}"
  case "$primeiro" in
    scripts/*)
      case "$primeiro" in
        *'*'*) ;;  # glob: quem expande é o shell, não dá para conferir aqui
        *) if [ ! -e "$RAIZ/$primeiro" ]; then
             AUSENTES+=("$id -> $primeiro")
             estado="ausente"
           fi ;;
      esac ;;
  esac
  case "$runner" in
    py|bash|bin|pytest) ;;
    *) echo "ERRO: runner desconhecido '$runner' no portão '$id'" >&2; exit 2 ;;
  esac
  G_ID+=("$id"); G_RUN+=("$runner"); G_ARGV+=("$argv"); G_ENT+=("${entradas:-}")
  G_ESTADO+=("$estado"); G_CHAVE+=(""); G_DICA+=(0)
  # a suíte inteira toca a máquina: nunca se lembra
  [ "$camada" = suite ] && G_ENT[${#G_ID[@]}-1]="@sempre"
done < <(_LISTA)
N=${#G_ID[@]}

# --- as vagas ----------------------------------------------------------------
#
# O SEMÁFORO DA CASA (`vez-do-pytest.sh`, três vagas divididas com todos os agentes em voo) conta o
# `pytest` de cada portão. Quem já roda DENTRO de uma vaga (o `vez-do-pytest.sh bash scripts/portoes.sh`
# de um agente) tem o descritor 9 preso a ela, herdado pelos filhos: aí os portões `pytest` não pedem
# vaga de novo (três corridas de agente, cada uma segurando uma vaga e esperando outra, se travariam
# para sempre) e rodam um de cada vez dentro da vaga que já têm. Sem o `vez-do-pytest.sh` (o CI, outra
# máquina) a fila do `pytest` tem três vagas em máquina de oito núcleos ou mais, e uma nas outras.
_NUCLEOS="$(nproc 2>/dev/null || echo 4)"
VAGAS_GERAIS="${PORTOES_VAGAS:-$(( _NUCLEOS > 3 ? _NUCLEOS - 2 : 1 ))}"
SEMAFORO=""
_vez="${HEFESTO_VEZ_DO_PYTEST:-$RAIZ/docs/process/ferramentas-da-leva/vez-do-pytest.sh}"
_dentro_da_vaga=0
case "$(readlink /proc/$$/fd/9 2>/dev/null || true)" in */vagas/vaga-*) _dentro_da_vaga=1 ;; esac
if [ "$_dentro_da_vaga" -eq 1 ]; then
  VAGAS_PYTEST=1
elif [ -f "$_vez" ]; then
  SEMAFORO="bash $_vez"
  VAGAS_PYTEST=3
else
  VAGAS_PYTEST=$(( _NUCLEOS >= 8 ? 3 : 1 ))
fi
VAGAS_PYTEST="${PORTOES_VAGAS_PYTEST:-$VAGAS_PYTEST}"
[ "$EM_SERIE" -eq 1 ] && { VAGAS_GERAIS=1; VAGAS_PYTEST=1; }
# tela e bus PRÓPRIOS de cada `pytest`, quando a máquina os tem
PREFIXO_DE_TELA=""
command -v dbus-run-session >/dev/null 2>&1 && PREFIXO_DE_TELA="dbus-run-session --"
command -v xvfb-run >/dev/null 2>&1 && PREFIXO_DE_TELA="${PREFIXO_DE_TELA:+$PREFIXO_DE_TELA }xvfb-run -a"

# --- a memória -----------------------------------------------------------------
[ -n "${CI:-}" ] && SEM_MEMORIA=1   # o CI mede de verdade, sempre
OUT="$LAR_DE_MENTIRA/saidas"
mkdir -p "$OUT"
MEM_PASTA=""
declare -A G_LINHA_DE=()
if [ "$SEM_MEMORIA" -eq 0 ] && [ "$N" -gt 0 ]; then
  _linhas=""
  for ((n = 0; n < N; n++)); do
    [ "${G_ESTADO[n]}" = rodar ] || continue
    _resolvido="${G_ARGV[n]}"
    [ "${G_RUN[n]}" = bin ] && _resolvido="$(_bin "${_resolvido%% *}") ${_resolvido#* }"
    G_LINHA_DE["${G_ID[n]}"]="${G_ID[n]}|${G_RUN[n]}|${_resolvido}|${G_ENT[n]}"
    _linhas+="${G_LINHA_DE[${G_ID[n]}]}"$'\n'
  done
  _chaves="$("$PY" "$RAIZ/scripts/recibo_da_medida.py" chaves --raiz "$RAIZ" \
             <<<"$_linhas" 2>"$OUT/memoria.err")" || _chaves=""
  [ -s "$OUT/memoria.err" ] && sed 's/^/  /' "$OUT/memoria.err"
  declare -A _CHAVE_DE=() _DICA_DE=()
  while IFS=$'\t' read -r _a _b _c; do
    case "$_a" in
      "#pasta") MEM_PASTA="$_b" ;;
      "") ;;
      *) _CHAVE_DE["$_a"]="$_b"; _DICA_DE["$_a"]="${_c:-0}" ;;
    esac
  done <<<"$_chaves"
  for ((n = 0; n < N; n++)); do
    [ "${G_ESTADO[n]}" = rodar ] || continue
    G_DICA[n]="${_DICA_DE[${G_ID[n]}]:-0}"
    _k="${_CHAVE_DE[${G_ID[n]}]:-}"
    [ -n "$MEM_PASTA" ] && [ -n "$_k" ] || continue
    G_CHAVE[n]="$_k"
    [ -e "$MEM_PASTA/${G_ID[n]}.$_k" ] && G_ESTADO[n]="lembrado"
  done
fi

# --- o que roda, e como --------------------------------------------------------
_comando_do_portao() {  # índice -> o comando (para `eval`, dentro da raiz)
  local i="$1" runner="${G_RUN[$1]}" argv="${G_ARGV[$1]}" cmd
  if [ "$runner" = pytest ]; then
    mkdir -p "$LAR_DE_MENTIRA/$i"/{config,data,cache,state,runtime,tmp}
    chmod 700 "$LAR_DE_MENTIRA/$i/runtime"
  fi
  case "$runner" in
    py)   cmd="$PY $argv" ;;
    bash) cmd="bash $argv" ;;
    bin)  cmd="$(_bin "${argv%% *}") ${argv#* }" ;;
    # `pytest` como runner nasceu em 25/08/2026, e por um defeito medido: o
    # `portao_a_casa_sabe_e_o_produto_nao_faz.py` RODA NO CI, ficou VERMELHO no
    # `dev` por horas, e ninguém viu — porque a lista local não o continha e o
    # portão da lista só compara `scripts/*`. Portão do CI que não cabe em
    # `scripts/` precisa caber aqui, ou o buraco continua aberto.
    # O `env` com o LAR DE MENTIRA é o que impede este runner de escrever na
    # casa dela — a razão inteira está no bloco «O LAR DE MENTIRA DO RUNNER
    # `pytest`», acima. Sem ele, este portão altera a configuração de quem está
    # usando o produto no mesmo instante. Em paralelo cada portão leva o SEU lar
    # (`$LAR_DE_MENTIRA/<índice>`): a substituição abaixo põe o índice no caminho
    # das seis variáveis, e o TMPDIR mora lá também.
    pytest) cmd="env ${_AMBIENTE_DE_MENTIRA[*]//$LAR_DE_MENTIRA/$LAR_DE_MENTIRA/$i} TMPDIR=$LAR_DE_MENTIRA/$i/tmp $PREFIXO_DE_TELA $PY -m pytest -q -p no:cacheprovider $argv"
            [ -n "$SEMAFORO" ] && cmd="$SEMAFORO $cmd" ;;
  esac
  echo "$cmd"
}

_roda_um() {  # índice: roda o portão e deixa a saída, os ms e, POR ÚLTIMO, o rc em $OUT
  local n="$1" cmd inicio fim rc
  cmd="$(_comando_do_portao "$n")"
  inicio=$(date +%s%N)
  ( cd "$RAIZ" && eval "$cmd" ) > "$OUT/$n.out" 2>&1
  rc=$?
  fim=$(date +%s%N)
  printf '%d' $(( (fim - inicio) / 1000000 )) > "$OUT/$n.ms"
  printf '%d' "$rc" > "$OUT/$n.rc.tmp" && mv -f "$OUT/$n.rc.tmp" "$OUT/$n.rc"
}

_escalona() {  # VAGAS ÍNDICE... : no máximo VAGAS portões ao mesmo tempo
  local vagas="$1" rodando=0 n; shift
  for n in "$@"; do
    while [ "$rodando" -ge "$vagas" ]; do wait -n 2>/dev/null; rodando=$((rodando - 1)); done
    _roda_um "$n" &
    rodando=$((rodando + 1))
  done
  wait
}

_mais_lentos_primeiro() {  # o que o portão levou da última vez decide quem sai antes; o resto, na ordem da lista
  local n
  for n in "$@"; do printf '%s %s\n' "${G_DICA[n]:-0}" "$n"; done | sort -s -k1,1nr | awk '{print $2}'
}

_mata_arvore() { local f; for f in $(pgrep -P "$1" 2>/dev/null); do _mata_arvore "$f"; done; kill "$1" 2>/dev/null || true; }
_interrompe() { local f; for f in $(jobs -p); do _mata_arvore "$f"; done; exit 130; }
trap _interrompe INT TERM

GERAL=(); DO_PYTEST=(); TODOS=()
for ((n = 0; n < N; n++)); do
  [ "${G_ESTADO[n]}" = rodar ] || continue
  TODOS+=("$n")
  if [ "${G_RUN[n]}" = pytest ]; then DO_PYTEST+=("$n"); else GERAL+=("$n"); fi
done

_nota_da_vaga=""
[ -n "$SEMAFORO" ] && _nota_da_vaga=" (pela vez-do-pytest)"
[ "$_dentro_da_vaga" -eq 1 ] && _nota_da_vaga=" (dentro de uma vaga que já é sua)"
echo "         vagas   ${VAGAS_GERAIS} gerais, ${VAGAS_PYTEST} de pytest${_nota_da_vaga}"
if [ "$SEM_MEMORIA" -eq 1 ]; then echo "         memória desligada"; else echo "         memória ${MEM_PASTA:-(indisponível)}"; fi
echo

INICIO_DA_CORRIDA=$(date +%s)
ESCALONADORES=()
if [ "$EM_SERIE" -eq 1 ]; then
  _escalona 1 ${TODOS[@]+"${TODOS[@]}"} & ESCALONADORES+=("$!")
else
  if [ ${#GERAL[@]} -gt 0 ]; then
    mapfile -t _ordem < <(_mais_lentos_primeiro "${GERAL[@]}")
    _escalona "$VAGAS_GERAIS" "${_ordem[@]}" & ESCALONADORES+=("$!")
  fi
  if [ ${#DO_PYTEST[@]} -gt 0 ]; then
    mapfile -t _ordem < <(_mais_lentos_primeiro "${DO_PYTEST[@]}")
    _escalona "$VAGAS_PYTEST" "${_ordem[@]}" & ESCALONADORES+=("$!")
  fi
fi

_escalonadores_vivos() {
  local p
  for p in ${ESCALONADORES[@]+"${ESCALONADORES[@]}"}; do kill -0 "$p" 2>/dev/null && return 0; done
  return 1
}

SOMA_MS=0
# --- a impressão, na ORDEM DA LISTA --------------------------------------------
for ((n = 0; n < N; n++)); do
  id="${G_ID[n]}"; runner="${G_RUN[n]}"
  case "${G_ESTADO[n]}" in
    ausente)
      printf '  %-22s AUSENTE DA ÁRVORE  %s\n' "$id" "${G_ARGV[n]%% *}"
      continue ;;
    lembrado)
      TOTAL=$((TOTAL + 1))
      LEMBRADOS+=("$id")
      _idade=$(( $(date +%s) - $(stat -c %Y "$MEM_PASTA/$id.${G_CHAVE[n]}" 2>/dev/null || date +%s) ))
      printf '  %-22s lembrado  (verde sobre os mesmos bytes, há %s)\n' "$id" \
        "$([ "$_idade" -ge 3600 ] && echo "$((_idade / 3600)) h" || echo "$((_idade / 60 + 1)) min")"
      continue ;;
  esac

  TOTAL=$((TOTAL + 1))
  while [ ! -e "$OUT/$n.rc" ]; do
    _escalonadores_vivos || { [ -e "$OUT/$n.rc" ] || break; }
    sleep 0.1
  done
  if [ -e "$OUT/$n.rc" ]; then
    rc="$(cat "$OUT/$n.rc")"; ms="$(cat "$OUT/$n.ms")"
    saida="$(cat "$OUT/$n.out")"
  else
    rc=125; ms=0; saida="o portão não terminou: a corrida foi interrompida antes dele"
  fi
  SOMA_MS=$((SOMA_MS + ms))

  # RC=0 NÃO É A MESMA COISA QUE «MEDIU», e a confusão entre as duas é a
  # família de defeito que esta casa mais caçou em 2026. Medido em 20/09/2026,
  # logo depois de o `sprints-fechadas` entrar: numa árvore SEM `docs/process/`
  # — que é como todo worktree de agente nasce, porque `git worktree add` não
  # copia arquivo ignorado — o portão imprimia, certinho, «NÃO MEDIDO: não há
  # docs/process/sprints/ nesta árvore», e esta linha aqui engolia a saída e
  # escrevia `sprints-fechadas ok`. Do lado de quem lê, verde sobre 46 sprints
  # que ninguém abriu — byte por byte o defeito que a cura do portão dizia ter
  # matado, mudado de andar.
  #
  # O CONTRATO, e ele vale para qualquer portão: quem NÃO PÔDE medir imprime
  # `NÃO MEDIDO` na PRIMEIRA linha e devolve 0. Ele não reprova (faltou o
  # dado, não o conserto) e também não passa por verde: sai nomeado, com a
  # razão dele à mostra, e conta separado no fim.
  # O casamento é por GLOB de `case`, não por fatia de string: `${s:0:10}`
  # conta BYTES sob `LC_ALL=C` e CARACTERES fora dele, e o `Ã` tem dois bytes
  # — a mesma linha acertaria e erraria conforme o ambiente de quem roda.
  nao_mediu=0
  case "$saida" in "NÃO MEDIDO"*) nao_mediu=1 ;; esac
  if [ "$rc" -eq 0 ] && [ "$nao_mediu" -eq 1 ]; then
    printf '  %-22s NÃO MEDIDO %5d ms\n' "$id" "$ms"
    printf '%s\n' "$saida" | sed 's/^/      /'
    NAO_MEDIDOS+=("$id")
  elif [ "$rc" -eq 0 ]; then
    printf '  %-22s ok      %6d ms\n' "$id" "$ms"
    pulos=""
    # PULO NÃO É VERDE. O pytest devolve 0 com teste pulado (sem tela, sem o
    # dado), e o portão sai `ok`: a linha diz quantos, e o recibo também, como
    # o recibo da suíte diz os dela. E portão com pulo NÃO fica na memória: o
    # que ele não mediu hoje ele tem de medir amanhã.
    if [ "$runner" = pytest ]; then
      pulos="$(printf '%s\n' "$saida" \
        | grep -E '^[= ]*[0-9]+ (passed|failed|skipped|xfailed|xpassed|errors?|deselected)' \
        | tail -1 | grep -o '[0-9]\+ skipped' | grep -o '[0-9]\+' || true)"
      if [ -n "$pulos" ]; then
        printf '      %s teste(s) pulado(s)\n' "$pulos"
        PULADOS+=("$id: $pulos teste(s) pulado(s)")
      fi
    fi
    # só o verde que MEDIU, sem pulo, entra na memória
    [ -z "$pulos" ] && [ -n "${G_CHAVE[n]}" ] && VERDES_TSV+="$id"$'\t'"${G_CHAVE[n]}"$'\t'"$ms"$'\n'
  else
    printf '  %-22s VERMELHO rc=%s %5d ms\n' "$id" "$rc" "$ms"
    printf '%s\n' "$saida" | sed 's/^/      /'
    VERMELHOS+=("$id")
  fi
done
wait 2>/dev/null
trap - INT TERM

# A CHAVE DE NOVO, DEPOIS DA CORRIDA: o portão mediu os bytes do meio da corrida, e a chave é a do começo.
# Se a árvore mudou enquanto ele rodava (alguém salvou um arquivo, deu `git add`), o verde dele não é o dos
# bytes da chave, e anotá-lo deixaria lembrado um verde que ninguém mediu. Só se anota a chave que não mudou.
if [ -n "$VERDES_TSV" ] && [ -n "$MEM_PASTA" ]; then
  _depois=""
  while IFS=$'\t' read -r _a _b _c; do
    [ -n "$_a" ] && _depois+="${G_LINHA_DE[$_a]:-}"$'\n'
  done <<<"$VERDES_TSV"
  _chaves_depois="$(printf '%s' "$_depois" \
    | "$PY" "$RAIZ/scripts/recibo_da_medida.py" chaves --raiz "$RAIZ" 2>/dev/null)" || _chaves_depois=""
  declare -A _CHAVE_DEPOIS=()
  while IFS=$'\t' read -r _a _b _c; do
    case "$_a" in "#"*|"") ;; *) _CHAVE_DEPOIS["$_a"]="$_b" ;; esac
  done <<<"$_chaves_depois"
  _confirmados=""; _mudaram=()
  while IFS=$'\t' read -r _a _b _c; do
    [ -n "$_a" ] || continue
    if [ "${_CHAVE_DEPOIS[$_a]:-}" = "$_b" ]; then
      _confirmados+="$_a"$'\t'"$_b"$'\t'"$_c"$'\n'
    else
      _mudaram+=("$_a")
    fi
  done <<<"$VERDES_TSV"
  [ ${#_mudaram[@]} -gt 0 ] \
    && echo "memória: a árvore mudou durante a corrida, e estes verdes não ficam lembrados: ${_mudaram[*]}"
  [ -n "$_confirmados" ] \
    && { printf '%s' "$_confirmados" | "$PY" "$RAIZ/scripts/recibo_da_medida.py" anotar --raiz "$RAIZ" || true; }
fi

PAREDE=$(( $(date +%s) - INICIO_DA_CORRIDA ))
echo
echo "tempo: ${PAREDE} s de parede; $((SOMA_MS / 1000)) s de portão somados; ${#LEMBRADOS[@]} lembrado(s) sem rodar."
if [ ${#AUSENTES[@]} -gt 0 ]; then
  echo "PORTÕES DECLARADOS E AUSENTES DA ÁRVORE (${#AUSENTES[@]}):"
  printf '  %s\n' "${AUSENTES[@]}"
fi
if [ ${#NAO_MEDIDOS[@]} -gt 0 ]; then
  echo "NÃO MEDIDOS (${#NAO_MEDIDOS[@]}): ${NAO_MEDIDOS[*]}"
  echo "  Faltou o DADO, não o conserto — eles não reprovam. Mas também não"
  echo "  entram na conta dos verdes: ninguém pode dizer que estão certos."
fi
_dos_lembrados=""
[ ${#LEMBRADOS[@]} -gt 0 ] && _dos_lembrados=" (${#LEMBRADOS[@]} lembrados de uma corrida anterior sobre os mesmos bytes)"
if [ ${#VERMELHOS[@]} -eq 0 ] && [ ${#AUSENTES[@]} -eq 0 ]; then
  if [ ${#NAO_MEDIDOS[@]} -gt 0 ]; then
    echo "VERDES — $((TOTAL - ${#NAO_MEDIDOS[@]})) de ${TOTAL} portões; ${#NAO_MEDIDOS[@]} NÃO MEDIDO(S)."
  else
    echo "TODOS VERDES — ${TOTAL} portões.${_dos_lembrados}"
  fi
  _sair 0
fi
echo "REPROVOU: ${#VERMELHOS[@]} vermelho(s) de ${TOTAL}${VERMELHOS[0]+ -> }${VERMELHOS[*]:-}"
_sair 1
