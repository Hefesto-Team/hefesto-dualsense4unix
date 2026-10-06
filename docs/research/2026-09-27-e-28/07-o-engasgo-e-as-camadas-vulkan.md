# O engasgo no jogo e as camadas Vulkan da Steam

O que se mediu, em 26/09/2026, sobre o engasgo periódico do Sackboy e a «cura» por camada Vulkan, e o que disso entrou no produto no mesmo dia.

**Etiquetas usadas abaixo:** MEDIDO (comando rodado, saída guardada) · LIDO
(código, commit, fonte) · RELATO (alguém disse, sem instrumento) · INFERIDO
(conclusão sem prova direta).

## 1. A resposta curta

- **Nunca houve medição de cura.** O único registro por quadro é o da madrugada
  de 22 para 23/08 (MangoHud, `log_interval=0`, cinco sessões). Nenhum log de
  quadro existe depois disso. As duas queixas de engasgo depois de 23/08 (07/09
  e 26/09) vieram com a camada **desligada** no prefixo.
- **A chave que a cura troca não tem leitor no caminho do jogo.** A cura troca o
  dword de `Software\[Wow6432Node\]Khronos\Vulkan\ImplicitLayers` no `system.reg`
  do prefixo. Um jogo DX12/DX11 sob vkd3d-proton ou DXVK não passa pelo
  carregador da Khronos (§3). O A/B de 23/08 comparou duas sessões em que a
  camada estava ausente nas duas.
- **O «funcionou» tem duas fontes:** a hipótese foi dada como «FORTE» antes de o
  A/B ser lido, e o jogo reaberto começa limpo (MEDIDO). O defeito nasce minutos
  depois de abrir, e toda mudança de camada vinha com um relançamento (§4).
- **Os dados apontam para o caminho do controle, não para o da imagem (INFERIDO
  forte).** A única vez medida em que o metrônomo parou no meio de uma sessão foi
  quando o daemon parou e os controles virtuais Sony sumiram (§2.3). Isso não
  basta para culpar o controle virtual nem o Hefesto.
- **O que mudou no produto em 26/09:** a Steam aberta pelo daemon passou a nascer
  fora do serviço (§6.1), e a aba Sistema parou de prometer cura de engasgo
  (§6.2, `D-2609-A-DICA-DO-VULKAN-NAO-PROMETE-CURA`).

## 2. O defeito, como foi medido em 23/08

### 2.1 A forma

Recalculado do dado cru por três contas independentes, com o critério «quadro
acima da mediana móvel + 12 ms» e os primeiros 90 s descartados:

| | `00-39-24`: camada LIGADA | `01-15-43`: camada DESLIGADA, ela jogando |
|---|---|---|
| duração | 29,8 min | 35,9 min |
| picos por minuto no regime | 70–72 | 112, depois 141–146 a partir do min 12 |
| intervalo dominante | 1,02 s | 0,5 s |
| duração do pico | 35 → 74 ms | 42 → 158 ms |
| crescimento por minuto | +2,24 ms/min | +4,11 ms/min |
| crescimento por pico | +0,0315 ms | +0,0296 ms |
| quadros por minuto, último minuto inteiro | 3.425 (min 28) | 2.523 (min 34) |

- **O período de 1,02 s tem fase solta do relógio de parede**, o que exclui um
  temporizador do sistema, mas não um laço do tipo «trabalha e dorme 1 s».
- **O custo cresce por evento, não por minuto.** No degrau de ritmo do min 12
  (112 → 141 picos/min), a inclinação por minuto sobe de ~3,2 para ~4,5 ms/min e a
  inclinação por pico fica entre 0,029 e 0,032 ms. Logo depois do degrau, os
  picos formam uma população só: o acumulador é único por processo.
- **O nascimento é em dois degraus**, a ~1,5 min um do outro. Na sessão ligada:
  18,4 ms até 8,3 min, um primeiro degrau de ~2 a 4 ms aos 8,4 min e o segundo,
  22,4 → 31,4 ms, aos 9,83 min. Na desligada: 17,8 → 22,9 ms aos 2,35 min e
  24,0 → 32,5 ms aos 3,85 min. A rampa de +0,03 ms por evento só começa depois do
  segundo degrau.
- **Os dois períodos da sessão desligada são a metade exata dos da ligada:** o
  metrônomo passa de 1,019 s para 0,505 s, e um segundo tranco lento passa de
  ~30,0 s para 14,8 s. Ninguém explicou; «carga de jogo diferente» não produz
  metade exata.
- **Caíram por medição:** GPU, VRAM e temperatura (51 % de uso, 65 °C); o próprio
  MangoHud (69,9 picos/min com ele e 70,7 sem).

### 2.2 O que o A/B não provou

- **As sessões não são comparáveis:** ela só jogava na desligada, as fases eram
  outras, e o jogo foi fechado e reaberto entre as duas.
- **A noite não é o caminho de 26/09.** Nas seis aberturas de 23/08 o daemon
  ligou a exceção do Steam Input (`steam_input_excecao_ativada`,
  `steam_input_fisico_escondido`), e a Steam criou oito `Microsoft X-Box 360 pad`
  a cada abertura. Nenhuma abertura depois de 26/08 teve essa exceção: em 26/09
  o jogo rodou sem Steam Input e, como HID Sony, só com os vpads `054C:0DF2`. O
  Proton também mudou, de GE-Proton10-34 para GE-Proton11-7.
- **Os controles estavam no rádio** (erros de CRC do DualSense por Bluetooth dentro
  das sessões). A eliminação do canal do controle («250,0 Hz por 60 s») foi feita
  no cabo, em 22/08, e não cobre esta noite.
- **A exclusão do daemon era por relato** (*«engasga com o Hefesto desligado»*),
  sem nenhum quadro gravado com o daemon parado por mais de 26 s.

### 2.3 O metrônomo parou junto com o daemon

A sessão `00-26-02` terminou 26 s depois de o daemon ser parado (00:34:02). Nos
30 s antes houve 36 picos acima de 28,7 ms; nos 25,9 s depois, 3, com mediana de
16,65 ms. Na hora da parada veio um quadro de 321,6 ms, quando os quatro vpads
saíram (MEDIDO). A prova é fraca: 40 s antes o metrônomo já tinha feito uma pausa
de 13 s, e 26 s é menos que o tempo de nascimento do defeito.

Quatro leituras preveem os mesmos 26 s, e nenhuma é separada pelo dado:

1. a reconexão zera o acumulador (no Windows, reconectar o controle zera o
   engasgo por um tempo);
2. o controle virtual Sony é o gatilho;
3. um laço do daemon é o metrônomo (o `02f8c2f09`, de 12/08, mostra que o daemon
   já teve varredura periódica do `/proc` a cada 2 s);
4. qualquer outro trabalho do daemon parado junto.

Contra a 2 fica o relato de engasgo com o Hefesto desligado: sem o Hefesto, o jogo
vê o DualSense físico, que também é Sony. A forma honesta da hipótese é «o
caminho de controle do jogo (o conjunto de aparelhos, e o Sony em particular)».

## 3. A cura por camada não tem leitor

Cada elo, LIDO na fonte (dos projetos de fora deste repositório) e MEDIDO nos
binários:

- O vkd3d-proton carrega o `winevulkan.dll` direto, de propósito (no fonte dele,
  o `main.c` do `d3d12core`, linhas 335-342: *«bypass issues with third-party
  overlays hooking the Vulkan loader»*). O DXVK faz o mesmo (o
  `vulkan_loader.cpp` dele, linhas 13-16, tenta `winevulkan.dll` antes de
  `vulkan-1.dll`).
- O `vulkan-1` do Wine (ramo `proton_11.0`) tem 30 linhas e só o `DllMain`; o
  `vkEnumerateInstanceLayerProperties` do `winevulkan` devolve `*count = 0`
  (no fonte do Wine, o `loader.c` do `winevulkan`, linhas 35-41). Os 31 prefixos da máquina
  medida usam o `vulkan-1.dll` embutido, e nenhuma pasta de jogo traz o seu.
- Das chaves Khronos do Vulkan, o executável do jogo só cita
  `SOFTWARE\Khronos\Vulkan\Drivers`, nunca `ImplicitLayers`. O único leitor e
  escritor da chave é o `EpicOnlineServicesUserHelper.exe`, que roda no
  lançamento, antes de o jogo nascer.
- O próprio manifesto da camada da Epic exige a variável
  `EOS_OVERLAY_ENABLE_VULKAN_WIN64=1` (`enable_environment`). Nem um carregador da
  Khronos a ligaria sem ela.

**A exceção, que impede dizer «em jogo nenhum».** O Proton prevê o carregador
oficial (`nativevulkanloader`, e o `PROTON_DLL_COPY` copia o `vulkan-1.dll` para o
prefixo), e o `winevulkan` se registra como driver dele. Nessa rota a chave tem
leitor, mas só para jogo **Vulkan nativo** que traga o carregador; um jogo DX12 ou
DX11 passa por fora dele mesmo assim.

**A camada não volta a ligar sozinha.** Os sete backups `.bak.hefesto-camadas-*`
guardam o valor de antes de cada escrita e alternam perfeitamente. Duas regravações
do `system.reg` por outra via (16/09 01:26 e 20/09 23:04) mantiveram `00000001`.

**O estado da chave no prefixo do jogo:** ligada até 07/09 12:27 (primeira escrita
da cura, pelo gancho de lançamento); desligada até 16/09 01:31, quando o botão a
devolveu; ligada até 20/09 23:00:39, quando o gancho a desligou de novo para uma
sessão de 4,0 min; depois, com o jogo fechado, o botão a alternou três vezes e a
deixou ligada; desligada desde 21/09 13:09:24. A sessão de 14/09, de 26,9 min com
a camada desligada, não teve queixa de engasgo (ausência de queixa, não prova de
cura), e as duas queixas (07/09 e 26/09) vieram com ela desligada:

- 07/09, 12:39: *«a correção do vulcan não tá funcionando.»* <!-- noqa-acento: citação literal -->
- 26/09, 14:33: *«tinhamos resolvido, ou perto disso com a descoberta da camada vulcan mas … parece que voltaram»* <!-- noqa-acento: citação literal -->

## 4. Por que pareceu funcionar

- **Em agosto não se mexeu na chave:** os dois manifestos da camada da Epic foram
  renomeados à mão para `.json.desligado`, entre 00:39:24 e 01:15:33 de 23/08, e
  voltaram às 03:19:20. O `system.reg` continuou em `dword:00000000`. A primeira
  escrita do produto no prefixo é de 07/09.
- **O jogo foi reaberto para a mudança** e ficou 2,6 min sem nenhum quadro acima
  de 33 ms (01:17:06–01:19:44). Comparado com o fim da sessão ligada (70 quadros
  longos por minuto, mediana de 71,5 ms), cada tranco da reaberta foi **menor** até
  o min 13–14. Quem compara pelo tamanho do tranco, que é o que o olho vê, vê
  «melhorou» por ~13 min.
- **A hipótese foi escrita como «FORTE» antes de o A/B ser lido.** O A/B só foi lido
  no commit das 03:34 (`751cb0893`, *«e o A/B derrubou a hipótese»*); nessa noite
  ela já tinha pedido a cura «contra o vulcan» para todos os jogos.
- **Nenhum outro teste ao vivo mediu nada.** Não houve log por quadro, e as
  sessões logo depois de cada mudança de camada foram de 3,5 e 3,8 min (07/09) e
  4,0 min (20/09), curtas perto do nascimento do defeito (2,3 a 9,8 min em 23/08).
- **A frase de que o Sackboy «saiu de 3.597 quadros engasgados para zero»**
  (`O-BOTAO-DO-VULKAN-NAO-RESPONDE-01`) é falsa em três pontos: 3.597 é quadros por
  minuto no melhor minuto da sessão ligada; não há medição depois da cura; e o A/B
  mediu o contrário.

**Outros ajustes do mesmo período, que não são a camada:** o
`VKD3D_CONFIG=no_upload_hvv` global desde 14/08 (feito para outro jogo, sem medição
de quadro, ativo em 26/09 e presente em 23/08, INFERIDO forte) e o
`vm.compaction_proactiveness` de 0 para 20 em 12/08 (tratou travamentos e falta de
memória, não o metrônomo, que foi medido depois).

## 5. As hipóteses, depois da conferência

| hipótese | a favor | contra | explica 23/08? |
|---|---|---|---|
| **o caminho de controle Sony do jogo** | o metrônomo parou com os vpads (§2.3); no Windows, o mesmo defeito, *«1 frame is frozen each second … larger and larger»*, aparece com o DualSense no caminho nativo e some fora dele; o custo cresce por evento, com acumulador único | 26 s de dado; ninguém reproduziu; em 23/08 havia Steam Input no meio | sim |
| outra camada no caminho da imagem | o overlay da Epic por gancho DX12 rodou a sessão inteira em 26/09; Reflex em «ligado + boost» com a NVAPI ligada pelo GE; sobreposição e fossilize da Steam; nenhuma foi desligada em teste | nenhuma para quando o daemon para; nenhuma tem período de 1 s conhecido | não o fim às 00:34 |
| o áudio Sony que o Hefesto publica | o device KS se apresenta como `USB\VID_054C&PID_0CE6\HEFESTOKS` | não existia em 23/08 | não |
| laços do daemon contra o servidor de som | três leituras de `pactl` com período de 0,94, 1,02 e 1,04 s | nasceram depois de 23/08 | não |
| a Steam e o jogo no cgroup e no nice do daemon | medido em 26/09 | não gera metrônomo | não |
| compilação de pipeline | `vkd3d-proton.cache.write` escrito durante a sessão | não é periódica | não |
| **a camada Vulkan da Epic pela chave** | — | ninguém lê a chave (§3) | **descartada** |

**O que o binário diz (MEDIDO por desmontagem).** A biblioteca de áudio do pad
embutida no jogo escolhe o ramo pelo PID e só conhece `05C4` e `0CE6`; o imediato
`0DF2` aparece zero vezes nela, e um `054C:0DF2` cai no `else`, sem abrir o áudio.
Quem reconhece o `0DF2` é o plugin `RawInput` da Unreal. Em 26/09, porém, os
botões apareciam como Sony e a vibração fina funcionava (RELATO): o device KS,
com PID `0CE6`, pode ser o que alcança o ramo de áudio (INFERIDO). Qual dos IDs a
biblioteca compara não se sabe.

**Os laços de ~1 s do daemon, com dono:** as três leituras de `pactl` saem de
`ler_quem_ouve`
(`src/hefesto_dualsense4unix/integrations/quem_ouve_o_microfone.py:304`), chamada
pela luz do microfone a `INTERVALO_DE_QUEM_OUVE_S = 1.0`
(`src/hefesto_dualsense4unix/daemon/subsystems/luz_do_mic.py:217`), desde
`82d04f960` (03/09). O vpad só responde `UHID_GET_REPORT` dentro de `pump_ff`
(`src/hefesto_dualsense4unix/integrations/uhid_gamepad.py:1213`), uma vez por
tique do laço de 60 Hz; o excesso de cada pico no início do defeito (~15–16 ms) é
perto de um tique. É compatível com o caminho do controle, não prova.

## 6. O que entrou no produto em 26/09

O texto registrado aqui é o de 26/09.

### 6.1 A Steam nasce fora do serviço

Em 26/09 a Steam aberta pelo botão PS rodava no cgroup do serviço do daemon
(MEDIDO), e com ela o jogo (INFERIDO forte, pela herança do cgroup): nice 5,
`OOMScoreAdjust=200` e `KillMode=control-group`, e um restart do daemon (o install
faz um) matava a Steam e o jogo. A mecânica «o jogo perde CPU para o compositor»
caiu: o compositor fica em outro grupo de CPU.

- **Dono novo:** `abrir`, em `src/hefesto_dualsense4unix/integrations/fora_do_servico.py`.
  Quando quem chama está num serviço, ou tem nice acima de 0, ou tem oom acima do
  piso do gerenciador de usuário, o aplicativo nasce numa unidade transitória
  (`systemd-run --user`, sem `--scope`), com `Type=exec` e `ExitType=cgroup`
  (`KillMode=process` antes do systemd 250), saída para o nada e o ambiente limpo
  por `--setenv`. Sem systemd de usuário, vale o `Popen` de antes.
- **Os chamadores:** o lançador da Steam (inclusive o `refocus_fallback_spawn`), o
  comando próprio do PS, a reposição dos lançadores, `start_steam_game` e
  `reopen_steam`.
- **Medido com um processo equivalente ao daemon** (nice 5, oom 200): pela cura o
  filho nasce com nice 0 e oom 100 (o piso do gerenciador), numa unidade própria, e
  sobrevive ao stop do pai; pelo `Popen`, nasce com 5/200 e morre. O `abrir` leva
  12 a 20 ms.
- **A conferência corrigiu dois defeitos:** a espera do `systemd-run` nasceu com
  10 s dentro do laço de leitura do daemon e poderia deixar os quatro controles sem
  entrada; caiu para 2,0 s, o mesmo teto do `pgrep` e do `wmctrl` do mesmo toque
  (`src/hefesto_dualsense4unix/integrations/fora_do_servico.py:63`, `50b403cdb`).
  E um comando que chegasse como texto pelo `daemon.reload` virava uma letra por
  argumento (`00f669bef`).
- **O comentário do nice** em `src/hefesto_dualsense4unix/daemon/main.py` dizia que
  o nice 5 «elimina o stutter», sem medição; passou a dizer o custo medido. O
  nice 5 continua.
- **Réguas:** `tests/unit/test_steam_fora_do_servico_01.py` (18 testes). Dez
  pedaços da cura arrancados, um por vez, e todos reprovaram.

### 6.2 A aba Sistema deixa de prometer cura

A dica *«Tira dos jogos a sobreposição Vulkan que engasga a imagem»* era uma
**regressão de 25/09** (`8fe83895b`): o texto anterior dizia «Tirar pode não
resolver o engasgo». A linha *«✓ OK · Nenhuma sobreposição picotando o jogo»* só
aparecia no desenho, na página antes da primeira pintura e na foto do README; o
produto em uso repinta o exame com a linha própria.

- **Decisão:** `D-2609-A-DICA-DO-VULKAN-NAO-PROMETE-CURA` (por delegação): a dica diz
  o que o ligável faz e que não cura engasgo; o rótulo «Corrigir Vulkan», que é
  dela, fica e vai à sessão dos desenhos.
- **A dica de 26/09** (`c3877af12`): *«Tira as sobreposições Vulkan que cada jogo
  deixa registradas dentro do Proton e guarda cópia. Quase nunca muda a imagem, e
  não cura engasgo. Desligar devolve o que foi tirado.»* «que cada jogo deixa»
  porque o motor preserva a camada da Steam e as ferramentas instaladas de
  propósito (`CAMADAS_PRESERVADAS`). «guarda cópia» e «devolve» foram conferidos
  em `_reescrever` e em `curar_todos(religar=True)`.
- **A linha do exame tem um dono só:** `frase_do_estado`, em
  `src/hefesto_dualsense4unix/integrations/camadas_vulkan.py`, usada pela aba e
  pelo desenho.
- **O fato errado saiu do módulo, do lançador, do install, do doctor e do
  manual:** o topo do módulo das camadas (o relato «engasga com o Hefesto
  desligado» ficou, marcado como relato), `assets/hefesto-launch.sh`, `install.sh`,
  `scripts/doctor.sh`, o rodapé de `frase_do_censo`
  (`src/hefesto_dualsense4unix/app/actions/emulation_actions.py`),
  `docs/usage/interface.md` e `docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md`. O que
  sobrou está em §8.
- **Réguas que mordem:** `test_a_dica_nao_promete_cura_de_engasgo`,
  `test_o_exame_do_desenho_diz_a_frase_que_o_produto_pinta` e
  `test_o_rodape_nao_poe_a_camada_na_frente_do_quadro`, em
  `tests/unit/test_o_botao_que_tira_o_que_faz_engasgar.py`, e
  `test_a_frase_da_linha_tem_um_dono_so`, em
  `tests/unit/test_o_vulkan_ve_todo_lancador.py`. Cada uma reprova quando a cura
  sai: a dica de 25/09 de volta, a linha «picotando» de volta, o rodapé antigo de
  volta, a frase montada à parte no pacote da aba.

## 7. Como medir o engasgo da próxima vez

- **Reabrir o jogo sempre parece curar.** Todo «funcionou» num defeito que nasce
  minutos depois de abrir precisa de **20 a 30 min** na mesma fase, comparando o
  **tamanho** dos quadros longos, não só a contagem, contra uma sessão de controle
  também reaberta.
- **O log por quadro pode não chegar pelo wrapper.** Em 23/08 mediu-se que
  `MANGOHUD=1` passado pelo wrapper não aparece no ambiente do jogo; só funcionou
  com a Steam inteira nascendo com a variável. Que o texto da opção de
  inicialização sobreviva (`d168ea850`) não prova que a variável chegue. O primeiro
  passo de qualquer ensaio é conferir que o CSV nasceu.
- **O ensaio que decide o caminho do controle (~40 min), na forma corrigida pela
  conferência:**
  1. portão do instrumento, 2 min: abrir, esperar, fechar pelo menu e conferir o CSV;
  2. S-D, 12 min: máscara DualSense desde a abertura, na mesma fase;
  3. S-X, 12 min: máscara Xbox nos quatro controles **antes** de abrir o jogo, para
     não haver reconexão dentro da medição, e conferir depois, no `Enum\HID` do
     prefixo, que nenhum `VID_054C` chegou ao jogo;
  4. braço de controle, opcional: dentro da S-D, depois de a grade nascer, um ciclo
     PS + L3 num controle só, de volta ao DualSense. Se a grade morre e renasce
     minutos depois, o zeramento por reconexão fica medido;
  5. se a S-X tiver grade: com o jogo aberto e parado, parar o serviço e esperar
     12 min. A grade morta que fica morta condena o daemon; a que renasce foi
     zeramento. Só então vêm as peças de imagem, uma por abertura (Reflex no menu do
     jogo; o overlay da Epic com `WINEDLLOVERRIDES=EOSOVH-Win64-Shipping=d`; a
     sobreposição da Steam).

  A leitura usa sempre os minutos ≥ 10 de cada sessão. A versão de 24 min com troca
  de máscara no meio da partida foi derrubada: a janela sem Sony (4 min) era mais
  curta que o nascimento do defeito e confirmaria a hipótese por construção.

## 8. O que ficou aberto

- **Se o engasgo voltou, e quanto.** Não há quadro gravado desde 23/08; a sessão de
  26/09 teve só ~4 min de foco no jogo.
- **Qual ID a biblioteca de áudio do jogo compara** (o HID `0DF2` ou o áudio `0CE6`
  do device KS), e se os `ContainerId` dos dois casam.
- **Por que o intervalo cai de 1,02 s para 0,5 s** quando ela joga, e por que o
  segundo tranco cai de 30 s para 14,8 s.
- **Se o overlay da Epic entra pelo gancho DX12** e se o gancho `WH_GETMESSAGE`
  dele processa cada `WM_INPUT` dos quatro vpads.
- **A latência do vpad a um `HidD_GetFeature`** do jogo, que ninguém mediu.
- **Os laços do daemon que existiam em 23/08** não foram auditados; só os dois de
  depois.
- **Por que o gancho curou em 20/09 23:00:39** se o «devolver» de 16/09 grava
  `escolha: manter`, e quem regravou o `system.reg` do jogo às 22:59:28.
- **A Steam fora do serviço, no aparelho:** falta ler o cgroup, o nice e o oom da
  primeira Steam aberta pelo PS depois do install; o systemd abaixo do 250 não foi
  medido; e, como a Steam aberta pelo PS agora sobrevive ao restart do install, o
  risco da `STEAM-NO-FISICO-01` vale para ela (INFERIDO).
- **Variáveis de ferramenta do terminal de quem roda o install chegam à Steam
  reaberta por ele** (`install.sh` roda `--reabrir-steam` pelo `Popen`), inclusive
  um token: o `ambiente_limpo` tira as de interpretador, e não essa classe. Tirá-la
  é decisão da `AMBIENTE-DO-JOGO-01`.
- **Em 26/09, a linha do Vulkan perdia 135 px na coluna do exame a 1212 px**,
  registrada em `CORTE_CONHECIDO_NO_DESENHO`
  (`tests/unit/test_a_janela_estreita_nao_engole_o_desenho.py`). Encurtar a frase e
  trocar o rótulo «Corrigir Vulkan» são perguntas da sessão dos desenhos.
- **O que a limpeza de 26/09 deixou para depois:** a foto
  `docs/usage/assets/aba-09-sistema.png` ainda mostrava «picotando», e os gerados do
  painel ainda não tinham a decisão nova; o texto antigo nos arquivos de tradução,
  os nomes dos testes `test_a_cura_do_engasgo_*` e a descrição do botão antigo em
  `docs/usage/interface.md` (anterior ao redesenho de 25/09, sem promessa de cura)
  não foram tocados.
- **As horas lisas de «sábado, 01/08»** não estão no log da Steam: a sessão longa
  daquela semana é de 02/08 (127,3 min), sem o `hefesto-launch` e antes dos ajustes
  de 12 e 14/08. Que caminho o jogo via nela não se sabe.
