# A revisão das sprints, 09/10/2026

Validador dos portões da leva 1-11, na árvore `valida-portoes` (base `829af7811`). O frontmatter
das sprints não foi tocado: o veredito mora aqui, e quem fecha é o `sprint.py fechar` no fecho.

**Os vereditos:** `concluída` (o código e a régua estão no ramo, e a sprint pode fechar),
`parcial` (há parte feita e falta o resto), `não feita`, `fora do repositório` (o trabalho mora na
casa e não no git) e `falso positivo` (a lista pegou uma sprint que já está fechada).

## As 32 abertas que não foram costuradas

A lista sai do `grep -L` da mesa. Nenhuma das 32 pode fechar hoje só com o que está no ramo.

| id | veredito | a prova | o que falta |
| --- | --- | --- | --- |
| A-GUARDA-FECHA-A-PORTA-01 | fora do repositório, parcial | o código está no staging, em `~/.local/state/hefesto-casa/leva-1-6/travas/` e em `hefesto-voo/travas-feito`; nada dele nos ganchos do zsh em `~/.config` | o gesto dela: `promover-travas.sh` |
| O-DESPACHANTE-DAS-REGRAS-DA-CASA-01 | fora do repositório, parcial | o `despachante.py` está só no staging; não está nos ganchos do zsh em `~/.config` | o mesmo gesto: `promover-travas.sh` |
| A-ARVORE-TEM-UMA-SESSAO-SO-01 | fora do repositório, parcial | a trava está no staging e não foi promovida | o mesmo gesto: `promover-travas.sh` |
| A-SENHA-SO-PASSA-PELO-ASKPASS-01 | fora do repositório, parcial | o `hefesto-criar-askpass.sh` não está em `~/.config`; só no staging | o mesmo gesto: `promover-travas.sh` |
| O-ENDERECO-NUNCA-CHEGA-A-CONVERSA-01 | fora do repositório, parcial | o `hefesto-mascara` não está em `~/.config`; só no staging | o mesmo gesto: `promover-travas.sh` |
| O-SHADPS4-QUE-JA-MORA-AQUI-01 | não feita | os testes e os arquivos que a sprint cria não existem | a leva 1.18, depois da 1.17, e a bancada |
| O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO-01 | não feita | os testes e os arquivos que a sprint cria não existem | a leva 1.18 e a bancada |
| O-SERVIDOR-DSU-LEVA-O-TOQUE-E-O-MOVIMENTO-AO-EMULADOR-01 | não feita | os testes e os arquivos que a sprint cria não existem | a leva 1.18 e a bancada |
| A-HISTORIA-REESCRITA-UMA-VEZ-SO-01 | parcial | os passos 1 a 11 foram feitos em 07/10; a sprint não tem código | o passo 12, que é do André |
| O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01 | parcial | a parte 0 foi costurada na 1.6 | as partes 1 a 4, de bancada e da casa, depois da 1.17 |
| A-DIVIDA-DA-BASE-DESCE-POR-ARQUIVO-E-POR-QUEM-TOCA-01 | não feita | `tests/mypy-limpos.txt` não existe | a sprint inteira, na leva da casa |
| O-CODIGO-SEM-NARRADOR-01 | falso positivo | a linha 3 diz `estado: feita` (07/10); o `estado: aberta` da linha 415 é texto do corpo, e o `grep -L` o pega | nada; quem refina a lista é o `grep` que lê só o frontmatter |
| O-COMENTARIO-COM-DOIS-PONTOS-SO-VALE-EM-CIMA-DE-ATRIBUICAO-01 | não feita | o teste que a sprint cria não existe | a sprint inteira, na leva da casa |
| AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01 | não feita | os dois testes novos não existem | a sprint inteira, na leva da casa, com `depois_de: A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01` (a colisão, abaixo) |
| AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA-01 | não feita | o instrumento `shas_citados.py` existe, mas a medida não foi feita | o passo 10 da janela |
| O-REPOSITORIO-NASCE-VIVO-01 | parcial | o mínimo e o github-completo estão no ramo: `repositorio.yml` com 27 funções, `scripts/github` e `tests/unit/test_o_repositorio_diz_o_que_o_github_tem.py` | o `profile/README` do `.github` da organização, o `ci.yml` e o ci-local com as imagens do `ghcr.io`, a Wiki e o aplicar inteiro depois do push; a prova por fora precisa de rede |
| SO-A-PRIMEIRA-LETRA-E-MAIUSCULA-EM-TODA-ABA-01 | não feita aqui | a régua não existe nesta árvore; a sprint está em voo no `valida-tela` | a costura do `valida-tela` |
| RELEASE-NO-CLONE-LIMPO-01 | parcial | as quatro divergências foram curadas em `726bbb7ba` | a primeira release do repositório novo, que é um gesto |
| A-FORJA-NAO-TRAVA-NO-APT-01 | não feita | `prova_do_apt_com_prazo.sh` não existe na Forja | a sprint inteira, na leva da casa |
| A-FORJA-SEM-RASTRO-01 | parcial | os itens 1 a 4 estão feitos; na Forja local, 0 ocorrências do nome do fornecedor em `--all` e em `origin/main`, e nenhum ramo com o prefixo da ferramenta | a prova dos contributors depois do chamado ao suporte; o `ls-remote` não foi medido |
| O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01 | não feita aqui | os testes não existem nesta árvore; a sprint está em voo no `valida-tato` | a costura do `valida-tato` |
| O-PAD-CEDIDO-CALA-O-GATILHO-E-A-LUZ-TAMBEM-01 | não feita aqui | os testes não existem nesta árvore; a sprint está em voo no `valida-tato` | a costura do `valida-tato`, ou a próxima leva |
| O-NUMERO-DA-BARRA-NAO-CONGELA-NO-VALOR-VELHO-01 | não feita | o teste que a sprint cria não existe | a próxima leva |
| O-BIG-PICTURE-SE-PROVA-NA-STEAM-E-O-MAPA-GANHA-AS-LINHAS-01 | não feita | `docs/data/mapa-controles.csv` tem 0 linhas de Big Picture | as linhas do mapa e a bancada dela |
| O-CODIGO-SEM-NARRADOR-02 | não feita | o `neutralizar-o-texto.py --conferir` diz que «faria em 35 arquivos»; a sprint dizia 5, então a leva 1-11 trouxe narrador novo | a sprint, com a lista medida de novo, na leva da casa |
| O-MOLDE-DA-SPRINT-LISTA-TODO-CAMPO-QUE-O-PORTAO-LE-01 | não feita | o molde não tem `apaga:`, que o `_CAMPOS_LISTA` lê; o teste não existe | a sprint inteira, na leva da casa |
| a sprint de 05/10 «…-CHEGA-COM-O-CONTEXTO-CERTO-02» | não feita | é texto, e é ela quem aprova | a aprovação dela |
| O-GITHUB-SEM-RASTRO-FORA-DO-GIT-01 | não feita | é o passo 11 da janela | a janela |
| a sprint de 08/10 «O-LOTE-DE-TESTES-…-ISOLA-O-WEBKIT-COMO-A-SUITE-01» | não feita | o `scripts/rodar-a-suite.sh` não tem modo lote | a sprint inteira, na leva da casa |
| O-DUALSENSE-PELO-RADIO-NO-WINE-SE-EXPLICA-01 | não feita | é só bancada, e o `MEDIDAS.md` não existe | a bancada |
| O-BASICO-MEDIDO-01 | não feita | o `doctor.sh` não tem `--basico` | a bancada e a leva da casa (L4) |
| A-CITACAO-CURTA-DO-DIFF-LE-A-CELULA-E-A-SEGUNDA-CHANCE-NAO-DESFAZ-A-CORRECAO-01 | não feita | os testes que a sprint cria não existem | a sprint inteira, na leva da casa |

## A amostra das costuradas: as 59 sprints da leva 1-11

Os 43 arquivos de teste que as 59 declaram em `cria:` rodaram nesta árvore pelo semáforo:
739 passed e 1 xfailed no lote comum (rc=0), e os quatro de WebKit, um por processo, com rc=0
(15, 8, 69 e 7 passed). Nas 19 sprints sem teste em `cria:`, a régua não foi conferida uma a uma.

| id | veredito | a prova | o que falta |
| --- | --- | --- | --- |
| A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01 | costurada (ultima-1-17) | sem teste em `cria:` | régua não conferida uma a uma |
| O-ECO-DO-ATO-SEM-OBJETO-01 | costurada (som-1-16), confere | `tests/unit/test_o_eco_do_ato_sem_objeto.py` verde na amostra | nada |
| A-TELA-PERGUNTA-AO-DONO-01 | costurada (ultima-1-17) | sem teste em `cria:` | régua não conferida uma a uma |
| O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01 | costurada (ultima-1-17), confere | `tests/unit/test_o_selecionar_acende_quem_esta_escolhido.py` verde na amostra | nada |
| SO-O-FREESTYLE-VALE-EM-TODO-JOGO-01 | costurada (perfis-1-17), confere | `tests/unit/test_so_o_freestyle_vale_em_todo_jogo.py` verde na amostra | nada |
| O-MODO-XBOX-NAO-E-QUEDA-02 | costurada (lancamento-1-11) | sem teste em `cria:` | régua não conferida uma a uma |
| A-LINHA-DA-COR-ESCOLHIDA-TEM-A-COR-DO-CONTROLE-01 | costurada (perfis-1-17), confere | `tests/unit/test_a_linha_da_cor_escolhida_tem_a_cor_do_controle.py` verde na amostra | nada |
| O-BROKER-VESTE-O-PID-QUE-O-PAD-PEDE-01 | costurada (nativo-1-12), confere | `tests/unit/test_o_broker_veste_o_pid_que_o_pad_pede.py` verde na amostra | nada |
| O-ICONE-DO-DOCK-E-O-DO-HEFESTO-01 | costurada (jogar-1-17), confere | `tests/unit/test_toda_porta_da_janela_veste_a_identidade.py` verde na amostra | nada |
| O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-02 | costurada (som-1-16) | sem teste em `cria:` | régua não conferida uma a uma |
| A-VIBRACAO-FINA-BATE-A-CADA-TIRO-01 | costurada (motor-1-13), confere | `tests/unit/test_a_vibracao_fina_bate_a_cada_tiro.py` verde na amostra | nada |
| O-ESTILO-DO-JOGO-LIGA-A-IMERSAO-INTEIRA-EM-TODO-MODO-01 | costurada (perfis-1-17), confere | `tests/unit/test_o_estilo_do_jogo_liga_a_imersao_inteira.py` verde na amostra | nada |
| A-LINHA-DO-EXTERNO-VOLTA-AOS-30-PX-E-A-COR-FORA-DA-LISTA-SE-ESCOLHE-01 | costurada (telas-1-11), confere | `tests/unit/test_a_cor_do_externo_fora_da_lista_se_escolhe.py` verde na amostra | nada |
| O-QUE-O-JOGO-MANDA-POR-TIRO-SE-CONTA-NO-PC-01 | costurada (contas-1-13), confere | `tests/unit/test_o_contador_do_que_o_jogo_manda.py` verde na amostra | nada |
| A-TRAVA-DO-LANCAMENTO-SOLTA-QUANDO-O-LANCAMENTO-ACABA-01 | costurada (lancamento-1-11) | sem teste em `cria:` | régua não conferida uma a uma |
| O-TIRO-VEM-DO-LADO-CERTO-01 | costurada (motor-1-13), confere | `tests/unit/test_o_tiro_vem_do_lado_certo.py` verde na amostra | nada |
| A-METRALHADORA-BATE-ENQUANTO-O-DEDO-APERTA-01 | costurada (gatilhos-1-17) | sem teste em `cria:` | régua não conferida uma a uma |
| A-MASCARA-ESCOLHIDA-E-O-QUE-O-JOGO-VE-EM-TODO-MODO-01 | costurada (jogo-ve-1-15) | sem teste em `cria:` | régua não conferida uma a uma |
| A-FAIXA-DO-TECLADO-SE-ACHA-01 | costurada (multi-1-14) | sem teste em `cria:` | régua não conferida uma a uma |
| O-START-DE-QUEM-NAVEGA-A-INTERNA-SO-GUARDA-01 | costurada (navegacao-1-15), confere | `tests/unit/test_o_start_de_quem_navega_a_interna.py` verde na amostra | nada |
| O-MUDO-DO-HEFESTO-CHEGA-AO-SOURCE-E-CADA-MEDIDOR-LE-O-SEU-01 | costurada (som-1-16), confere | `tests/unit/test_o_mudo_do_hefesto_chega_ao_source.py` verde na amostra | nada |
| O-DISPARO-E-A-ARMA-SEMI-AUTOMATICA-MANDAM-O-MODO-DE-ARMA-01 | costurada (cegas-1-13) | sem teste em `cria:` | régua não conferida uma a uma |
| O-PADRAO-DO-ALTO-FALANTE-DESLIGA-SEM-PERFIL-ATIVO-01 | costurada (telas-1-11) | sem teste em `cria:` | régua não conferida uma a uma |
| A-08-MOSTRA-O-DESENHO-DO-CONTROLE-E-O-HUB-PERGUNTA-A-ENTRADA-01 | costurada (conexoes-1-17), confere | `tests/unit/test_a_08_mostra_o_desenho_do_controle.py` verde na amostra | nada |
| OS-ULTIMOS-LEITORES-DE-TEXTO-DE-FORA-PERGUNTAM-AO-DONO-01 | costurada (som-1-16), confere | `tests/unit/test_o_mic_monitor_nao_deixa_a_supervisora_viva.py`, `tests/unit/test_o_udev_se_pergunta_a_biblioteca.py` verde na amostra | nada |
| A-LATENCIA-DO-TATO-SE-MEDE-SEM-A-MAO-DELA-01 | costurada (contas-1-13), confere | `tests/unit/test_a_latencia_do_tato_se_mede_sem_a_mao_dela.py` verde na amostra | nada |
| AS-QUATRO-LINHAS-DA-08-SEM-DONO-GANHAM-DONO-OU-SAEM-DO-DESENHO-01 | costurada (telas-1-11) | sem teste em `cria:` | régua não conferida uma a uma |
| A-LUZ-RESPIRA-A-CADA-TIRO-01 | costurada (motor-1-13), confere | `tests/unit/test_a_luz_respira_a_cada_tiro.py` verde na amostra | nada |
| A-LUZ-DO-MIC-PISCA-COM-QUEM-OUVE-DE-FORA-01 | costurada (som-1-16), confere | `tests/unit/test_a_luz_do_mic_pisca_com_quem_ouve_de_fora.py` verde na amostra | nada |
| O-P1-VIBRA-NO-APARELHO-DELE-COMO-OS-OUTROS-01 | costurada (motor-1-13), confere | `tests/unit/test_o_p1_vibra_no_aparelho_dele.py` verde na amostra | nada |
| O-TATO-VIVO-SO-FALA-ONDE-O-JOGO-CALA-01 | costurada (motor-1-13), confere | `tests/unit/test_o_tato_vivo_so_fala_onde_o_jogo_cala.py` verde na amostra | nada |
| O-JOGO-PODE-APAGAR-E-IGUALAR-A-FABRICA-O-QUE-O-COMPUTADOR-DIZ-01 | costurada (perfil-1-11), confere | `tests/unit/test_o_jogo_apaga_o_que_o_computador_diz.py`, `tests/unit/test_o_jogo_iguala_a_fabrica_e_vale.py` verde na amostra | nada |
| O-SOM-DO-TIRO-SAI-TAMBEM-NO-CONTROLE-01 | costurada (motor-1-13), confere | `tests/unit/test_o_som_do_tiro_sai_tambem_no_controle.py` verde na amostra | nada |
| A-OPCAO-QUE-A-STEAM-DESFAZ-APARECE-NO-DOCTOR-01 | costurada (lancamento-1-11), confere | `tests/unit/test_a_opcao_que_a_steam_desfaz_aparece_no_doctor.py` verde na amostra | nada |
| O-NOME-DO-JOGADOR-TEM-UM-DONO-SO-01 | costurada (telas-1-11) | sem teste em `cria:` | régua não conferida uma a uma |
| A-REGUA-DOS-EFEITOS-DO-GATILHO-LE-O-BLOCO-COMO-O-CONTROLE-LE-01 | costurada (gatilho-1-13), confere | `tests/unit/test_os_efeitos_do_gatilho_mandam_o_que_o_nome_diz.py` verde na amostra | nada |
| O-PAD-CEDIDO-AO-P1-NAO-FALA-COM-O-APARELHO-QUE-CEDEU-01 | costurada (pads-1-14) | sem teste em `cria:` | régua não conferida uma a uma |
| O-TECLADO-SO-DENTRO-DO-JOGO-TEM-DONO-01 | costurada (navegacao-1-17), confere | `tests/unit/test_o_teclado_so_dentro_do_jogo_tem_dono.py` verde na amostra | nada |
| O-GATILHO-VIRA-CLIQUE-SEM-LIGAR-O-CURSOR-01 | costurada (navegacao-1-17) | sem teste em `cria:` | régua não conferida uma a uma |
| O-SOM-DE-CADA-PAD-NA-ORDEM-DO-HIDRAW-01 | costurada (pads-1-14), confere | `tests/unit/test_o_som_de_cada_pad_na_ordem_do_hidraw.py` verde na amostra | nada |
| O-PERFIL-ANTIGO-DE-VIBRACAO-POR-POSICAO-CARREGA-NO-PISO-01 | costurada (ultima-1-17), confere | `tests/unit/test_o_perfil_antigo_de_vibracao_por_posicao_carrega_no_piso.py` verde na amostra | nada |
| A-CALIBRAR-GRAVA-O-ZERO-DESCONTA-EM-TODO-CAMINHO-E-CABE-A-940-PX-01 | costurada (calibrar-1-17), confere | `tests/unit/test_o_zero_so_vale_se_foi_gravado.py`, `tests/unit/test_o_angulo_do_giro_desconta_o_vies.py` verde na amostra | nada |
| A-LINHA-DO-SALVAR-DIZ-O-GESTO-E-O-QUE-MUDOU-01 | costurada (perfil-1-11), confere | `tests/unit/test_a_linha_do_salvar_diz_o_gesto_e_o_que_mudou.py` verde na amostra | nada |
| O-CONTROLE-VOLTA-AO-LINUX-QUANDO-O-HEFESTO-NAO-SOBE-01 | costurada (nativo-1-12), confere | `tests/unit/test_o_controle_volta_ao_linux_quando_o_hefesto_nao_sobe.py` verde na amostra | nada |
| O-STOP-DO-SOM-TEM-ORCAMENTO-E-NAO-PERGUNTA-AO-SERVIDOR-MUDO-01 | costurada (nativo-1-12), confere | `tests/unit/test_o_stop_do_som_tem_orcamento.py` verde na amostra | nada |
| A-COR-ESCOLHIDA-ACOMPANHA-O-CONTROLE-01 | costurada (jogar-1-17), confere | `tests/unit/test_a_cor_escolhida_acompanha_o_controle.py` verde na amostra | nada |
| A-MASCARA-DUALSENSE-DO-UINPUT-SEGUE-O-VID-01 | costurada (jogo-ve-1-15) | sem teste em `cria:` | régua não conferida uma a uma |
| TODO-TEXTO-QUE-ABRE-UMA-LINHA-COMECA-COM-MAIUSCULA-01 | costurada (ultima-1-17) | sem teste em `cria:` | régua não conferida uma a uma |
| A-GRACA-DO-JOGO-NAO-JOGA-FORA-O-PRIMEIRO-EFEITO-01 | costurada (pads-1-14), confere | `tests/unit/test_a_graca_do_jogo_nao_joga_fora_o_primeiro_efeito.py` verde na amostra | nada |
| A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01 | costurada (multi-1-14), confere | `tests/unit/test_a_ponte_se_conta_em_fatias_no_ar.py` verde na amostra | nada |
| A-RAMPA-DE-FORCA-CHEGA-AO-FUNDO-E-A-VIBRACAO-SALVA-NAO-PERDE-A-FREQUENCIA-01 | costurada (gatilho-1-13) | sem teste em `cria:` | régua não conferida uma a uma |
| NO-DESLIGADO-A-STEAM-NAO-SE-METE-E-O-JOGO-MANDA-01 | costurada (perfis-1-17), confere | `tests/unit/test_no_desligado_a_steam_nao_se_mete.py` verde na amostra | nada |
| O-ARCO-E-O-GALOPE-MANDAM-O-MODO-QUE-O-CONTROLE-LE-01 | costurada (cegas-1-13) | sem teste em `cria:` | régua não conferida uma a uma |
| O-GATILHO-DIZ-QUANDO-DISPAROU-01 | costurada (cegas-1-13), confere | `tests/unit/test_o_gatilho_diz_quando_disparou.py` verde na amostra | nada |
| O-232-SAI-E-A-CONTA-DA-PONTE-ENTRA-01 | costurada (contas-1-13), confere | `tests/unit/test_o_232_nao_volta_aos_textos.py` verde na amostra | nada |
| A-PONTE-SE-OTIMIZA-ATE-QUATRO-NO-ULTRA-NUM-ADAPTADOR-01 | costurada (multi-1-14), confere | `tests/unit/test_a_ponte_se_otimiza_ate_quatro_no_ultra.py` verde na amostra | nada |
| O-RESTAURADOR-DO-LANCAMENTO-SOLTA-QUANDO-O-JOGO-ACABA-01 | costurada (nativo-1-12), confere | `tests/unit/test_o_restaurador_do_lancamento_solta_quando_o_jogo_acaba.py` verde na amostra | nada |
| O-SINAL-SE-MEDE-EM-DOIS-ADAPTADORES-01 | costurada (multi-1-14) | sem teste em `cria:` | régua não conferida uma a uma |
| O-GATILHO-ACOMPANHA-O-RITMO-DO-TIRO-01 | costurada (motor-1-13), confere | `tests/unit/test_o_gatilho_acompanha_o_ritmo_do_tiro.py` verde na amostra | nada |

## A colisão entre A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01 e AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01

O código já cumpre a ordem **A-TELA-SEM primeiro**. Ela está costurada e mexeu em
`tests/unit/test_toda_excecao_tem_sprint_que_a_tira.py` (`f294673ec`, `7a5f184ad` e `553a2f199`).
A AS-REGUAS está aberta e não foi implementada. Então quem ganha a espera é a AS-REGUAS:
`depois_de: A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01`.

O `check_colisao_de_sprints.py` dá OK nas três árvores porque a posse corrigida do arquivo só
existe na cópia de `docs/process` da árvore `ultima-1-17`
(`~/.local/state/hefesto-casa/leva-1-11/costura/ultima-1-17.md`, linhas 171 e 233). Ela não
chegou à mesa nem à integração. O `depois_de` e a posse vão para a sprint na costura.
