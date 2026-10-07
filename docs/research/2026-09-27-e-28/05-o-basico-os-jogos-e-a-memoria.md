# O básico medido nos jogos e o ensaio da memória

O que se mediu em 27 e 28/09/2026 para escrever o protocolo do básico, rodar a bancada de jogos da noite, saber o que falta para outra máquina reproduzir o produto e preparar o ensaio da memória do engasgo.

> **Por que este documento existe.** A noite de 27/09 queria provar o produto
> dentro de jogos de verdade, com os quatro controles no rádio e sem a mão de
> ninguém. Metade do que se aprendeu é sobre o produto; a outra metade é sobre
> os instrumentos, que mediam outra coisa. As duas metades se perdem se ficarem
> só nas medidas cruas.

## 1. A mesa medida

Entre 19h50 e 20h20 de 27/09:

- os quatro controles no rádio, em três adaptadores; nenhum no cabo;
- o Freestyle em modo Xbox: 3 pads uinput «DualSense Edge» `054c:0df2` e 1 Xbox `045e:028e`, com `canal_sem_imu`;
- o teclado na tela do COSMIC (`cosmic-osk`) manda uns 20 pedidos de vibração nulos por segundo a cada pad;
- 30 jogos da Steam, todos com o atalho do Hefesto e no GE-Proton11-7; um jogo do Heroic no GE-Proton10-34, fora do pino.

**O multiplicador de pads não está curado.** O boot das 19h10 criou 1 pad uhid e 6 uinput para 4 jogadores (o P1 nasceu 4 vezes em 5,3 s). O `dev` foi a `400a1257e` às 20h36 com a `f89421d7d`, e o boot seguinte fez de novo 1 uhid + 6 uinput, com 2 `coop_ordem_recriada recriar=['p1']`. A `f89421d7d` não cura o multiplicador. Do kernel ao daemon, a espera ficou em ≤ 1 ms por pad nos dois boots.

## 2. O protocolo do básico

O protocolo `o_basico` (sprint `O-BASICO-MEDIDO-01`) pode nascer dos ensaios que já existem. Dos 76 `.py` de `scripts/ensaios/`, 72 são instrumentos: 14 servem ao básico (5 pedem extensão), 5 à fase dos jogos, 11 dependem da mão dela, 10 são históricos, 5 ficam fora e 23 são de tela. Seis têm defeito: quatro obsoletos e dois que mentem na mesa de hoje.

O que o protocolo tem de resolver, medido:

- **As sondas não viajam.** Tudo o que o protocolo usava morava numa pasta ignorada pelo git, e o pacote não leva `scripts/ensaios` (`packaging/arch/PKGBUILD` instala uma lista sem ela). Proposta: as sondas passam a ser versionadas em `scripts/`, a saída vai para o diretório de estado do usuário (`XDG_STATE_HOME`), e o protocolo entra como `hefesto-dualsense4unix basico`, achado pelo mesmo `encontrar_arquivo_do_repo` do doctor.
- **No modo Xbox o lado do jogo fica cego.** O `comum.descobrir_aparelhos` (`scripts/ensaios/comum.py`) só varre `/sys/class/hidraw`, e o `src/hefesto_dualsense4unix/integrations/no_do_vpad.py` recusa nome repetido; os três pads uinput homônimos saem com `per_vpad[].evdev = None`. O `uinput_gamepad._create_device` não passa `phys`, e o pad sai com o `py-evdev-uinput` padrão. Proposta: nascer com `phys="hefesto-vpad/<n>"`, dono `A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01`; até lá, casar pad e jogador por um pulso de FF lido no delta de `per_vpad[].ff_nao_nulo_count`.
- **Quase toda escrita pelo IPC deixa estado.** `led.set`, `trigger.set` e `led.player_set` com `uniq` entram na camada da usuária, que sobrevive a hotplug e vence todo perfil automático; o `trigger.reset` com `uniq` grava `trigger_off()` pela mesma porta. O `gamepad.mask.set` e o PS + R3 gravam no perfil ativo. Logo, a volta do subcomando `saidas` é o reinício do daemon, declarado; a régua é zero `override_do_perfil_cedeu_ao_ajuste_manual` no primeiro jogo depois. O `state_full` não publica essa camada; proposta: `controllers[].camada_da_usuaria`.
- **O `led.auto_release` não faz nada desde 14/09** (`7e426bd3b`): o `_handle_led_auto_release` (`src/hefesto_dualsense4unix/daemon/ipc_handlers.py:1211`) só registra no diário e devolve `ok`. A docstring ficou; é fato errado a tirar.
- **Os dois modos se medem sem gravar arquivo** (hipótese até conferir os sha256): `gamepad.emulation.set {enabled, caminho}` sem `origin` vira `origin="profile"` e escreve só o caminho da sessão. O PS + R3 cicla dualsense → xbox → mouse_teclado e grava o perfil ativo a cada aperto.
- **O vendor:product do pad uhid é `054c:0df2`**, não `054c:0ce6` (`src/hefesto_dualsense4unix/integrations/uhid_gamepad.py:103`; `src/hefesto_dualsense4unix/integrations/uinput_gamepad.py:109`: «NUNCA o 0x0ce6 do físico»). O que distingue os pads é o nome e os nós: o uhid se chama «DualSense Wireless Controller (Hefesto Pn)», tem hidraw e os nós «Motion Sensors» e «Touchpad»; o uinput se chama «Sony Interactive Entertainment DualSense Edge…», com `Phys=py-evdev-uinput` e sem hidraw.
- **«Parar no primeiro vermelho» trava tudo hoje**, por causa do multiplicador. A linha 1 vira 1a (agora: pads = jogadores) e 1b (no boot: pads criados = jogadores), e a parada segue a dependência de alvo.
- **A saída dos ensaios não é de máquina.** `scripts/ensaios/entrada_em_repouso.py` e `scripts/ensaios/quem_e_quem.py` devolvem rc=0 sempre; há 15 funções de máscara próprias em `scripts/ensaios`, e nenhuma cobre as formas do endereço usadas pelo microfone e pelo endpoint de háptica. O protocolo passa toda saída por um mascarador só; ensaio sem `--json` sai «não sei», nunca verde.
- **O contador de vibração está contaminado pelo teclado na tela:** `ff_play_count` ≈ 53 mil por pad com `ff_nao_nulo_count = 0` nos quatro. O critério da vibração pedida pelo jogo é o delta de `ff_nao_nulo_count`.
- **O microfone pelo rádio se mede sem ligá-lo:** `controllers[].hz_voz` (100,0 no P3) e o bit de áudio do relatório de entrada. Gravar da fonte do microfone liga o microfone pelo rádio.

## 3. A bancada de jogos da noite

O roteiro: PRAGMATA (3357650) no modo DualSense, Future Knight (4235410) no Xbox com máscaras divididas, Sackboy (1599660) com os quatro, DON'T SCREAM (2497900) com o microfone, e o PRAGMATA com as features somadas. A Steam sobe por `systemd-run --user` e o jogo abre por `steam://rungameid`.

**O PRAGMATA rodou no modo Xbox**, sem giroscópio nem touchpad: o modo DualSense entrou às 21:07:35, caiu para o Xbox 12 s depois, e às 21:08:07 o produto recusou a volta com o jogo aberto (`vpad_recriacao_bloqueada_por_jogo`). Pertence à `O-MODO-XBOX-NAO-E-QUEDA-02`.

**A háptica pelo rádio em silêncio não é zero:** de 22 a 23 mil relatórios de 142 B por controle em 300 s de menu.

**A premissa «sem foco, só o modo entra» caiu.** O lançamento ativa o perfil inteiro do jogo desde 22/08 (`ELO-MUDO-01`, `src/hefesto_dualsense4unix/daemon/launch_env.py:769`, `_ativar_o_perfil_do_lancamento` em `:940`). Mas, com o jogo vivo e o foco em outra janela, o autoswitch devolve o Freestyle em 12 s (`DEFAULT_DEBOUNCE_SAIDA_SEC`, `src/hefesto_dualsense4unix/profiles/autoswitch.py:38`). Só o modo fica, preso pelo R-04 enquanto o jogo vive. A `FOCO-ERRANTE-01` só cobre a janela do cliente Steam. Candidata: generalizar a guarda para que o jogo vivo segure o próprio perfil contra janela que não é de jogo (régua: jogo vivo e outra janela em foco por 13 s, e o perfil segue).

**A escada grava confirmação falsa.** Jogo sem carimbo começa a escada no lançamento (`src/hefesto_dualsense4unix/daemon/launch_env.py:815`), e o silêncio confirma aos 180 s (`SILENCIO_CONFIRMA_SEC`, `src/hefesto_dualsense4unix/integrations/ponte_escada.py:179`) sem perguntar se alguém jogou; o carimbo vai para o perfil do jogo. Só cinco appids tinham carimbo. Proposta: o silêncio só confirma se houve entrada nos físicos na janela (régua em lar de mentira: jogo vivo, nenhuma entrada, 181 s, nenhum carimbo).

**Os instrumentos do lado do jogo mediam outra coisa:**

- a sonda de núcleo atribuía por nome do fio: quem escreveu nos pads foram `HIDAPI Rumble`, `wine_sechost_se`, `winedevice.exe` e o fio da Steam, nunca o `.exe` do jogo, e o critério «48 B com o nome do jogo» dá zero sempre. Cura: chavear por pid e agrupar por árvore de processo;
- o `o_jogo_segura_o_nosso_no` não sonda pad uinput, então no modo Xbox nunca dá «o jogo segura os quatro»;
- o `taxa_no_hidraw` mede taxa, não intervalo;
- o `o_jogo_para_de_ver_o_giro --so-medir` força `SDL_JOYSTICK_HIDAPI=0` e mede o SDL pelo evdev, não o hidraw que o Proton usa;
- o resumo lia só a primeira e a última amostra, e cruzava pads recriados no delta de `per_vpad`.

**O que a bancada sem ela não prova:** o sinal (tiro, mira, voz). Não há IPC de entrada no pad e a Forja não estava compilada. A noite prova a corrente: fluxos, contadores, nós seguros, o silêncio pelo rádio.

**O que se descartou:** comparar o PRAGMATA (DualSense) com o Future Knight (Xbox) muda jogo, engine, modo, máscaras e perfil de uma vez. Mede-se cada modo, não a diferença; a comparação no mesmo jogo é o PS + R3 dela, por último, porque cada aperto recria os pads com o jogo aberto (o gesto dela fura o R-04: `ORIGENS_GESTO_DELA`, `src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py:94`).

**Anonimato.** O `state_full` expõe o serial de fábrica inteiro (17 caracteres), que o mascarador da noite não cobria; o diário do jogo trouxe 7 linhas com o nome da ponte de som com os octetos 4 e 5 à mostra, e os perfis copiados crus traziam 4 identidades cada. Regra que fica: a cópia byte a byte de restauração vai para pasta privada 0700; na medida, só o sha256 e a cópia mascarada.

**A noite deve rodar como unidade do `systemd --user`.** O terminal da sessão gráfica morre com ela; o `systemd --user` tem linger e atravessou as três quedas de 27/09.

## 4. O produto em qualquer máquina

Sprint `O-PRODUTO-EM-QUALQUER-MAQUINA-01`: treze lacunas e uma escada de prova sem outra máquina (P0 retrato; P1 install em lar de mentira; P2 primeira pintura; P3 contêiner; P4 VM com passagem USB; P5 segunda conta; P6 outro chip). As altas:

- **O microfone pelo rádio nasce ligado sobre um patch de kernel que só esta máquina carrega.** Com microfone em `None`, «o microfone LIGA» (`src/hefesto_dualsense4unix/utils/maquina.py:441`). Sem o patch 0003 do `hid-playstation` (não está no upstream), o driver lê o quadro de áudio como estado de gamepad: desliga o microfone e mexe cursor e teclado (medido em 10/09). O doctor não tem check desse DKMS. Proposta: o 0003 expõe uma marca só de leitura, o daemon só põe o microfone no ar com ela, o patch vai ao linux-input (`O-MICROFONE-DO-RADIO-PERGUNTA-AO-DRIVER-01`, proposta).
- **O BlueZ que segura quatro no rádio não chega a máquina nenhuma.** O passo 3f do `install.sh` só consome o backport já construído; um Pop!_OS novo recebe o 5.72, sem o `hefesto-0002` (a cura da queda de 22/09). Sem dpkg, o doctor diz «info». Proposta: publicar os `.deb` no release, e warn fora do dpkg; o install segue sem construir o backport sozinho (824 MB e restart do bluetoothd).
- **Todo número do rádio foi medido num chip só**, três TP-Link UB500 Realtek (`2357:0604`); nenhum é interno. `N_MAX_PONTES = 2` é «Provisório» (`src/hefesto_dualsense4unix/integrations/radio_da_mesa.py:363`), e o doctor não diz o modelo. Proposta: teto por modelo, 2 como piso (`O-RADIO-CONHECE-O-CHIP-01`, proposta).

As médias, em uma linha cada:

- a `.venv` da bancada vê o `evdev` 1.7.0 do apt (veio com o input-remapper); quem instala recebe o 2.0.0, que nenhum aparelho rodou (`pyproject.toml:30` pede `evdev>=1.6`, sem trava). Proposta: um `constraints.txt` (`AS-VERSOES-QUE-A-CASA-MEDIU-01`, proposta);
- o `hid-playstation` do Hefesto é o fonte 7.0.11 e roda no 7.1.5 sem `BUILD_EXCLUSIVE_KERNEL` (o do `uhid` tem); perde a rejeição de `num_touch_reports` inválido do DS4;
- Secure Boot sem MOK pode deixar o DualSense sem driver, e as mensagens do install falam só do Nintendo (hipótese: aqui o Secure Boot está desligado e o aviso nunca rodou);
- a bancada esconde variáveis: o compositor recompilado (`dpkg -V` acusa o binário), o grupo `input` (quem chega usa só o uaccess), a GPU NVIDIA, o input-remapper e o teclado na tela, que é de toda sessão COSMIC;
- o install termina sem dizer «reinicie», embora «vale no próximo boot» apareça em 26 lugares;
- o Freestyle de fábrica (`assets/profiles_default/freestyle.json`) não tem `policy`, microfone, brilho no teto nem modo, e a `O-FREESTYLE-E-UMA-CAMADA-SO-01` não tem o asset na posse;
- a Steam do Flathub fica sem wrapper e com o pino adiado, e a Steam instalada depois do Hefesto nunca foi medida (`A-MAQUINA-LIMPA-01`, proposta);
- parear do zero pelo produto nunca foi provado; `docs/usage/bluetooth.md` chama o pareamento de manual, e em 27/09 o `README.md` exigia o cabo na primeira vez;
- o cmdline do kernel só se escreve por kernelstub;
- a primeira corrida do Pytest unit do CI em 32 dias (corrida 36343737322) deu 615 failed e 1.584 errors num clone limpo: 1.492 linhas são `ModuleNotFoundError: gi` (dona `O-CI-DA-DEV-VOLTA-A-VERDE-01`);
- armadilha para o P3: `scripts/ci/instalar_como_usuaria.sh` faz `chown -R` da raiz; a árvore entra no contêiner por `git archive`, só leitura.

## 5. O ensaio da memória (ensaio 5 do engasgo)

O ensaio 5 da `O-ENGASGO-SE-CURA-PELO-QUE-CHEGA-AO-JOGO-01` mede a memória com o PRAGMATA no menu em três voltas: com a afinação de memória da máquina, sem ela, e sem ela e sem o daemon. A ordem dela para o ensaio: «usa o mango hud na steam», e «cuidado pra algo não encerrar o terminal nem interface gráfica».

**A afinação da máquina não é do Hefesto, e «sem ela» não é o padrão do kernel.** A bancada tem um arquivo de sysctl próprio (swappiness 180, page-cluster 0, `watermark_scale_factor` 200, `watermark_boost_factor` 0, `vfs_cache_pressure` 200, `min_free_kbytes` 524288, `extfrag_threshold` 100), nascido do `NVRM: Out of memory` em memória de sistema. Sem ele, a máquina volta aos valores do Pop (swappiness 180 e page-cluster 0 do zram, `watermark_scale_factor` 125, `min_free_kbytes` ≈ 162885) e do kernel (`vfs_cache_pressure` 100, `extfrag_threshold` 500). Só quatro chaves mudam de fato. Um serviço de manutenção da máquina roda `sysctl --system` sem condição a cada hora (pula a rodada com jogo da Steam aberto), religa parte das unidades paradas e o próprio timer se o achar desabilitado; o gancho do apt roda o mesmo script mesmo com o timer parado. Nada do Hefesto reescreve `vm.*` sozinho.

**O MangoHud pela Launch Option, sem desenhar:**

```
MANGOHUD=1 MANGOHUD_CONFIG=no_display=1,log_interval=0,autostart_log=1,log_duration=0,output_folder=<pasta que exista>
```

Provado no fonte da versão instalada (0.6.9-1): com `MANGOHUD_CONFIG` presente o arquivo de config global não é lido; `no_display=1` pula o desenho e mantém o log; `log_interval=0` grava um quadro por linha; a pasta tem de existir, sem `, : ; =` e com até 255 bytes. O CSV se chama `<programa>_<AAAA-MM-DD_HH-MM-SS>.csv`; `frametime` em ms (CPU, de present a present), `elapsed` em ns; o `_summary.csv` não sai com `log_duration=0`, e não faz falta (cada linha tem flush). **A primeira linha é lixo:** em 27/09 deu 91.648.200 ms, o uptime. Um erro de digitação no `MANGOHUD_CONFIG` faz o HUD aparecer.

**Pelo código, a variável atravessa o atalho.** O atalho termina em `exec env "$@"` (`src/hefesto_dualsense4unix/integrations/steam_launch_options.py:79-86`; `assets/hefesto-launch.sh:779`), e o wrapper não filtra o `"$@"`. O que não está medido é se o `MANGOHUD` chega ao `environ` do jogo: em 23/08 a casa mediu que não chegou, com suspeita de ter lido o processo errado. O ensaio tem trava: o `environ` do `PRAGMATA.exe`, o `libMangoHud` em `/proc/<pid>/maps` e o CSV crescendo; sem isso, para.

**A escrita vai pelo dono, a tabela de opções por jogo (`D-2109`).** Uma edição direta no `localconfig.vdf` é desfeita pelo `hefesto-steam-input-guard` no primeiro tique com a Steam fechada. Simulada sobre cópia, a ida muda uma linha só e a volta devolve o arquivo idêntico. O `--aplicar` não é atômico (`src/hefesto_dualsense4unix/integrations/opcoes_por_jogo.py:316`) e devolve 3 («adiado») enquanto a Steam ou o `steamwebhelper` estiverem de pé.

**A revisão do script achou 16 defeitos antes de ele rodar**; os que valem para qualquer ensaio que para e devolve estado:

1. um serviço `oneshot` rodando aparece como `activating`, nunca `active`: esperar por `active` não espera nada;
2. `trap - EXIT INT TERM` devolve o TERM ao padrão, e o `TimeoutStopSec` de 90 s mata a devolução no meio; a unidade leva `-p TimeoutStopSec=15min` e caminho absoluto;
3. a marca de «parei» se grava antes do ato, não depois;
4. todo `sudo` se prova sem TTY antes de mudar algo (`SUDO true`), e todo `sysctl -w` se relê;
5. parar um `.path` ou `.timer` não para o `.service` que ele já disparou;
6. o PID do jogo se relê: o primeiro candidato pode ser o avaliador da Steam;
7. os CSV de cada volta vão para a pasta da volta, senão se misturam;
8. a ordem fixa com → sem → sem-e-sem-daemon acumula fragmentação e page cache: não separa o efeito da afinação do efeito da ordem; proposta: uma quarta volta «com» de novo;
9. sem a afinação, a volta tem de vigiar o `NVRM` e interromper; o earlyoom não protege o terminal;
10. a volta sem daemon muda também o que o atalho exporta ao jogo.

O resultado do ensaio não entrou neste registro.

## O que ficou aberto

- O multiplicador de pads no boot (1 uhid + 6 uinput para 4 jogadores), que a `f89421d7d` não curou.
- O modo DualSense que cai para o Xbox 12 s depois de entrar, com o PRAGMATA aberto (`O-MODO-XBOX-NAO-E-QUEDA-02`).
- O Freestyle que volta por cima do jogo vivo aos 12 s de foco fora dele: a guarda generalizada espera decisão.
- A escada que confirma ponte sem ninguém jogar.
- O `led.auto_release` morto e a camada da usuária fora do `state_full`.
- O `phys` do pad uinput e o mascarador único.
- As quatro sprints propostas do §4 (`O-MICROFONE-DO-RADIO-PERGUNTA-AO-DRIVER-01`, `O-RADIO-CONHECE-O-CHIP-01`, `AS-VERSOES-QUE-A-CASA-MEDIU-01`, `A-MAQUINA-LIMPA-01`), não criadas.
- Dela: instalar qemu/ovmf e ceder um adaptador e um controle à VM; um adaptador de outro chip; a segunda conta; o cabo e a volta pelo rádio (o controle volta sozinho em 60 s sem o PS?); se o pino do Proton vale também para o Heroic; o serial inteiro no «Copiar».
- Se o `MANGOHUD` atravessa o atalho até o jogo, e o resultado do ensaio da memória.
