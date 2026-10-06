# A auditoria de 27/09: o que falta para o produto terminar

Nove auditorias só de leitura sobre as sprints de 26 e 27/09/2026 e sobre o produto inteiro, e uma síntese que as junta numa ordem de trabalho (27/09/2026).

> **Como ler as citações.** Todo `arquivo:linha` abaixo é o do código de
> 27/09. As curas que vieram depois moveram linhas (o
> `_a_escolha_dela_sem_o_vazamento`, por exemplo, estava em
> `lifecycle.py:304-346` e em 28/09 começava na 566). Na dúvida, procure o
> nome da função; a linha é o endereço daquele dia. Caminho que começa em
> `app/`, `daemon/`, `integrations/`, `interface/` ou `profiles/` é relativo a
> `src/hefesto_dualsense4unix/`; nome de arquivo solto (`lifecycle.py`,
> `gamepad.py`…) é o único com esse nome no repositório.

## O que se auditou

Nove eixos, cada um com achados classificados em gravidade (alta, média,
baixa) e confiança (medido ou hipótese):

| eixo | achados | altos |
|---|---:|---:|
| 01 · as sprints de 27/09 | 15 | 1 |
| 02 · o que fechou em 26/09 | 9 | 1 |
| 03 · a matriz de adaptação (modo × máscara × transporte × jogador) | 13 | 1 |
| 04 · as abas conversam | 13 | 4 |
| 05 · acessibilidade e uso | 10 | 4 |
| 06 · o jogo roda liso | 11 | 1 |
| 07 · os instrumentos e o básico | 12 | 1 |
| 08 · a autoria no versionado | 10 | 5 |
| 09 · pronto para o mundo | 17 | 6 |

A síntese fundiu 23 achados duplicados, decidiu 19 conflitos entre eixos
conferindo no código, no git e no CI, e tirou deles quinze ações em ordem.

## Três fatos que a síntese corrigiu

- A integração estava **um** commit à frente do `dev`, não sete; a cura do
  censo de coleta (`d0188111c`, `1a05fa114`) já estava no `dev`.
- O CI do `dev` **não fica verde desde 22/08 às 04h53 UTC** — 61 corridas
  vermelhas seguidas, de 26/08 a 27/09. Nelas o passo «Censo de coleta»
  reprovava e o `Pytest unit` ficava pulado. As sprints `VERDE-NAO-E-PROVA-01`
  («desde 26/09») e `O-CI-DA-DEV-VOLTA-A-VERDE-01` («desde pelo menos 20/09»)
  datavam errado. Na corrida do `d587a737f` o censo passou e o `Pytest unit`
  rodou pela primeira vez em 32 dias: o que ele reprovar é **medida, não
  regressão**.
- A `O-MODO-XBOX-NAO-E-QUEDA-01` estava `feita`, não aberta.

## A ordem das quinze ações

1. **O modo tem um dono** (`O-MODO-XBOX-NAO-E-QUEDA-02`, nome que
   `gamepad.py:1195` já citava sem arquivo de sprint).
2. **O endereço do controle não sai da máquina**: as linhas versionadas em
   ordem invertida, o «Copiar» da aba 09, a aba 10 e os **cinco**
   mascaradores do produto (não dois).
3. O pad uhid atende desde que nasce, e a vibração sai da trava.
4. A troca de controle não para o laço.
5. O clique duplo não apaga perfil nem desfaz alternância.
6. Um aplicador e uma receita de gravação — antes, a `O-SALVAR-E-O-APLICAR-LEEM-O-PERFIL-01`
   corrigida, porque partia de premissa que caiu com `7c07ec336`.
7. O CI verde de verdade.
8. O protocolo do básico.
9. A entrada e o engasgo medidos por par.
10. O mapa diz o que o produto faz.
11. A háptica obedece ao sinal e chega a quem entra depois.
12. Nada só do P1 nem só do BT.
13. O Freestyle vira camada.
14. A janela se alcança sem mouse.
15. O que vai para o mundo sai limpo, e só então a 0.9.4.6.

## 1. O modo fora do jogo tinha dois donos

`src/hefesto_dualsense4unix/daemon/lifecycle.py:304-346` devolvia a cada boot
todo `xbox` do `gamepad_caminho.flag` a `dualsense` e gravava
`motivo=escrito_pelo_vazamento_do_gesto_no_jogo` — uma causa que o código
nunca conferiu, e que desde 19/09 não podia mais acontecer (o gesto dentro do
jogo não escreve o global, `gamepad.py:1457-1468`). A função roda em todo boot
(`lifecycle.py:623`), contra a própria docstring («UMA VEZ»). O outro dono era
o `mode.caminho` do perfil Freestyle.

Medido no diário de 27/09: PS + R3 às 01h34 fora de jogo gravou `xbox` no
Freestyle; às 05h28 o boot devolveu, subiu `dualsense` e dois segundos depois
`xbox` de novo. No restart das 13h49 **o P1 nasceu 4 vezes em 3,3 s** (1 uhid
e 3 uinput): 7 pads para 4 jogadores. Desde 13h50 os quatro estavam no modo
Xbox, sem movimento, touchpad nem háptica.

A promoção do *connect* também trocava o modo Xbox por DualSense (12h52 e
16h15); `ba5c786b4` curou isso às 16h23. Ficaram sem caminho o *revive*
(`gamepad.py:1194`) e a volta do Steam Input (`gamepad.py:585`, que guarda só
a máscara).

A cura proposta: um dono só, com a origem gravada (`{caminho, origem, quando}`);
a migração roda uma vez de fato, com marca, e diz `origem=desconhecida` em vez
de afirmar causa; um `reerguer_o_p1(daemon, motivo)` que lê o caminho como o
`coop._caminho()` já faz. Régua: flag `xbox` com origem de gesto fora do jogo
dá um start e um pad por jogador; a mordida (devolver a migração) faz o P1
nascer duas vezes.

## 2. O endereço do controle vaza por quatro caminhos

- **No versionado, em ordem invertida.**
  `docs/data/ensaios-brutos/2026-08-15-TROCA-DE-BRACOS-os-mesmos-quatro-nos-dois-transportes.txt:348-349`
  (dumps 0x09 e 0x0b) trazem os seis octetos de um controle da bancada, de trás
  para a frente e separados por espaço, desde 16/08 e já empurrados; e
  `docs/data/ensaios-brutos/2026-08-15-IDENTIDADE-o-cracha-nos-dois-transportes.csv:4,14`
  expõe um terceiro endereço no byte 25 do 0x0b. Nenhum dos portões vê essa
  forma: `scripts/check_o_endereco_em_toda_forma.py` só aceita `[:-]` e a
  ordem direta, e `tests/unit/test_docs_mac_anonimato.py` só lê a ordem
  direta. A `O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01`, marcada `feita`, não
  fecha.
- **No «Copiar» da aba 09.** `interface/pacotes/a09_sistema.py:2245-2257` tem
  três expressões (separada, colada, `_<6hex>`) e nenhuma casa a forma
  `HEFESTO<6hex>` do endpoint de háptica; a mesma linha do diário leva o
  `uniq=` mascarado ao lado do sufixo. A função do produto, rodada sobre o
  diário real: em **393 linhas desde 01/09** o endereço inteiro se reconstrói
  depois da máscara — **136 de 136** desde 26/09.
- **Na aba 10.** `app/actions/perfis_web.py:154-166` (`_id_visivel`) mostra o
  `uniq` cru como «ID da peça», contra o glossário.
- **No MAC do pad virtual.** `uhid_gamepad.vpad_mac` (`:665-672`) é um blake2b
  de 4 bytes sem sal do endereço real; com a máscara ao lado sobram 65.536
  candidatos, e um endereço sintético saiu em 57 ms.

A cura: um dono único das formas do endereço (as duas ordens, os separadores
`[:_\-. ]`, a colada e a `HEFESTO<6hex>`), importado pelas réguas e pelo
produto — e virando processador do log do daemon, para o diário já nascer
mascarado. Mascarar as quatro linhas versionadas antes de qualquer reescrita
de história.

## 3. A conversa entre as abas (eixo 04, quatro altos)

- **O Freestyle como camada deixaria sem destino tudo que se grava fora do
  jogo.** Há três resolvedores do perfil que recebe a gravação
  (`interface/pacotes/perfil.py:78`, `rodape.py:627`, `profiles/manager.py:1472`).
  Sem perfil ativo, 5 escritores calam, 10 recusam mandando à aba Perfis e 5
  escritas do daemon viram `sem_perfil`. A posse da
  `O-FREESTYLE-E-UMA-CAMADA-SO-01` cobre 8 dos 24 arquivos que dependem do
  Freestyle e põe em `nao_toca` o `rodape.py`, que ela quebra. Proposta: uma
  sprint antes, `O-DESTINO-DA-GRAVACAO-TEM-UM-DONO-01`, e a do Freestyle em
  duas (A: camada e aplicador; B: o registro de fora do jogo e o fim do
  `freestyle.json`).
- **A sprint do Salvar parte de premissa caducada.** Desde `7c07ec336` (25/09,
  `O-BOTAO-DO-MIC-GRAVA-NO-PERFIL-01`) o botão do microfone grava no perfil, e
  o mudo mora em três lugares (perfil, sessão, aparelho), com dois escritores
  no mesmo clique. A favor da cura: os 29 perfis da bancada passados por
  `DraftConfig.from_profile` e `to_profile` num lar de mentira saíram sem
  nenhuma diferença.
- **O «Aplicar» e a ativação são duas máquinas.** O `to_ipc_dict`
  (`app/draft_config.py:1151`) não leva o mudo, o volume e o ganho do
  microfone, os sensores, a máscara, a mira nem o modo;
  `daemon/ipc_draft_applier.py:459-490` descarta o mudo; a economia tem duas
  cópias. Proposta: `O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01`, com um
  `profile.reaplicar(name, secoes)`.
- **Um arraste de força na Vibração ativa o perfil inteiro como troca
  manual.** `perfil.gravar_e_reaplicar` (`perfil.py:305`) manda
  `profile.switch`: grava a sessão, arma a trava de 30 s do autoswitch,
  reaplica tudo e esquece a lembrança do microfone. Medido no diário de 26/09:
  `origin=manual` às 19:19:52 e 19:19:53, um por clique, com o jogo aberto.
  Há **cinco receitas** diferentes de gravar um campo entre as abas.

Médios: a economia só vale na ativação e os gestos ao vivo da 03 e da 04
passam por baixo dela; o alvo de saída do daemon fica preso depois de abrir um
cartão na 08 ou testar na 05, e nada devolve ao «Todos»; o nome dado ao
controle só aparece na 08 (as outras leem `controles[k].cor`, que ninguém mais
escreve); a aba Navegação não liga a Navegação e a linha laranja culpa um jogo
que não está aberto; o clique duplo tem duas regras (a 06 desfaz, as outras
sete alternâncias repetem).

## 4. Acessibilidade e uso (eixo 05, quatro altos)

- **A «Navegação Interna» aparece ligada e não existe.**
  `interface/paginas/06-navegacao.html:3813` publica «Ligada — cada controle
  navega o Hefesto»;
  `a06_navegacao.py:2969-2973` a põe em `SEM_GESTO`. Quem só tem o controle
  depende do P1 no modo Navegação mirando alvos de 16–17 px.
- **O essencial não se alcança sem mouse nem por leitor de tela.** Na 01,
  19 de 27 alvos não recebem foco (o Modo, as 12 máscaras, os chips da fita);
  na 10, 21 de 36; 77 dos 96 «?» não têm `tabindex`, e o «?» é onde mora a
  explicação da tela. Nenhuma régua cobre foco.
- **A recusa é uma borda de 1 px que pisca 1,5 s**
  (`folha_da_casa.py:17-20`), e o motivo só vai para o log da janela: 132
  recusas no diário, 70 desde 13/09, com frases que diziam o que fazer. Na
  deuteranopia simulada o verde e o laranja ficam com contraste de 1,1:1
  entre si. `aria-live` aparece zero vezes.
- **Os alvos por controle têm 16 a 19 px**, o «?» 17 px, o puxador dos
  deslizantes 12 px; o mínimo da WCAG 2.5.8 é 24×24.

Médios: o «Remover» da aba Perfis apaga com um clique duplo em menos de 8 s
sem conferir o rótulo armado (`a10_perfis.py:2497`), e a volta só existe
na linha de comando; não há `:focus-visible` na casa; três vocabulários para
força e bateria; letra de 10 a 14 px sem zoom (415 declarações entre 10 e
12 px contra 37 de 14 px ou mais).

A maior parte é **conserto puro** — `tabindex`, `role`, `aria-*`, uma região
viva escondida, área de toque invisível — publicável sem mudar pixel se a
lista `INVISIVEIS` de `scripts/check_o_desenho_aprovado.py` aceitar esses
atributos. O que muda pixel vai à sessão dos desenhos.

## 5. O jogo roda liso (eixo 06)

**O alto:** toda troca de controle (conectar, cair, mudar de máscara, recriar
o virtual) para a entrada dos quatro de **0,24 a 5 s**. O `coop.sync` roda
dentro do laço de 60 Hz (`lifecycle.py:3791`) e leva junto
`launch_env.materialize_launch_env`, que relê e reescreve os **4,2 MB** do
`system.reg` do prefixo do Heroic para o device KS. Medido no diário: 257
regravações desde 26/09, mediana 380 ms, p95 867 ms, máximo 5.027 ms, 11 acima
de 1 s. Enquanto isso não rodam o repasse nem o `pump_ff`. Cura: na borda, só
os `.env` pequenos; o resto vai para o sossego (`armar_rematerializacao` já
existe), uma vez por rajada.

Os médios dizem que **o que sustenta a fluidez não está medido**:

- Com jogo aberto, o virtual tem mais buracos acima de 33 ms que o físico
  (180 × 28, 173 × 80, 121 × 31 no PRAGMATA; 70 × 41 e 76 × 36 no Sackboy;
  máximo de 1.018 ms). A afirmação «o daemon não cria o buraco» vinha de 30 s
  sem jogo. O instrumento soma por processo e não casa o virtual N com o
  físico N, nem separa a reconexão. **O dono do buraco ainda não está
  provado** (a síntese ficou com o eixo 07 contra o 06).
- A troca de máscara do ensaio 2 muda duas variáveis de uma vez: o caminho
  Sony e a taxa (`MOTION_EMIT_MAX_HZ=250`, 945 a 962 relatórios/s no uhid
  com quatro virtuais, ~12 chamadas ao wineserver por relatório).
- O «sem afinação» dos ensaios volta aos padrões do kernel, mas o Pop de
  fábrica já tem swappiness 180; as fases são n=1, em ordem fixa. Proposta:
  três condições com nome (a máquina afinada, o Pop de fábrica e o kernel),
  ordem ABBA, n ≥ 3.
- O xalia sobe em **todo** Proton (Valve e GE) e lê os controles pelo SDL3.
- O «Corrigir Vulkan» junta overlay e fossilize, que têm efeitos opostos.
- O Modo Jogo do lançador só fala com o `system76-power`
  (`assets/hefesto-launch.sh:256-341`); fora do Pop é um no-op calado.

Baixos: os dados crus da noite se perderam (só ficaram resumos); os 41 fios do
daemon têm o mesmo nome no kernel; `launch_env.py:1018-1019` põe política de
cache de shader da NVIDIA em todo jogo, sem medida.

## 6. A matriz de adaptação (eixo 03)

**O alto (hipótese):** a háptica por áudio só chega a quem estava na mesa
quando o jogo abriu. `integrations/audio_ks_dualsense.py:432-449` reescreve os
blocos KS só com os presentes, e `:584-600` recusa com o wineserver vivo. Quem
entra depois, volta de um -71 ou troca USB↔BT fica sem háptica, e nada avisa;
a primeira sessão de todo jogo novo também. Proposta:
`A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01`, com identidade por lugar (P1–P4) e
blocos pré-provisionados para os quatro.

**P2–P4 têm menos que o P1** em três lugares: os atalhos do PS
(`daemon/subsystems/poll.py:55-74` só ouve o posto de P1), a Navegação
(`mouse.py:116-138` usa só o primário; o touchpad é o do primeiro nó do
kernel) e a env do lançamento (`launch_env.py:1072`, a máscara do P1 decide
`SDL_JOYSTICK_HIDAPI=0` para todos). O modo publicado também sai da máscara do
P1 (`ipc_handlers.py:79-98`).

**O produto afirma o falso em dois lugares:**
`integrations/canal_sem_imu.py:80-91` diz que o modo Xbox perde a vibração,
e o pad uinput a entrega (`uinput_gamepad.py:426-457`); e o mapa diz que a
háptica não aciona em transporte nenhum, quando vibrou no USB em 17/09 e no BT
em 18/09 — com `tests/unit/test_vibracao_e_gatilho_no_radio_o_caminho_escrito.py:280-311`
trancando a frase errada. E 50 das 114 linhas do DualSense em
`docs/data/mapa-controles.csv` não têm data.

Outros médios: o par modo Xbox + máscara DualSense nunca foi medido num jogo;
o PID por jogo para o giroscópio nas libScePad antigas tem a pré-condição
cumprida (o físico escondido desde 24/09) e a sprint nunca foi escrita; com um
adaptador só, `governador_do_radio.py:691-699` concede a terceira ponte além
do teto que derrubou os controles em 22/09. Baixos: testar a vibração de um
controle cala o rumble do jogo nos quatro (`gamepad.py:785`); os mods DSX só
endereçam o índice 0 (`daemon/udp_server.py:327-344`).

## 7. Os instrumentos e o básico (eixo 07)

- **Três diagnósticos de 27/09 não se sustentavam como escritos** (o de que
  «o daemon não cria o buraco» está na seção 5; o dos 60 s, logo abaixo). A
  queda das 12h43 não foi a espera circular do `open`: o pad nasceu 0,53 s
  antes do registro e ficou 26,2 s sem ninguém atender a vibração. A das
  12h52 — a terceira, com a assinatura da noite (registro 29,8 s depois de o
  pad nascer) — não estava escrita. A favor da cura: desde 13h07, 16 pads
  criados, zero pânico.
- **O pedido de 60 s da mão dela já estava respondido**: o PRAGMATA espelha a
  vibração nos quatro (163 × 156, 73 × 71 e 39 × 39 segundos com vibração em
  algum × nos quatro). Regra que sai: relato que mede o que a sprint pede
  reescreve a sprint no mesmo dia.
- **A conferência dela não mede o aparelho.**
  `scripts/check_a_conferencia.py` tem 7 linhas; seis leem HTML ou
  código no processo, e a da cor lê a cor *pedida*. O socket é fixo em
  `/run/user/1000`. O `scripts/doctor.sh` tem 90 verificações de ambiente e
  só três por controle. Proposta: `O-BASICO-MEDIDO-01`, uma conferência do
  aparelho (um `o_basico.py --veredito`, a criar em `scripts/`) e um
  `scripts/doctor.sh --basico` só de leitura.
- **As sondas mexem no que medem.** Com a palavra dela em `None`,
  `dualsense_bt_audio.py:1060` deixa um gravador ligar o microfone pelo rádio
  (~106 quadros/s no link) — e o microfone aberto nos quatro derruba a entrada
  de 260,4 para 170,5 Hz (`:76-77`). Toda sonda passa a declarar o que mexe.
- A régua do pad promete 5 ms e mede 500 ms; a cura depende do nome interno
  `UInput._find_device` do python-evdev, com `evdev>=1.6` sem teto.
- Fatos derrubados de pé: a `A-FAIXA-NA-MESA-FORA-DE-ORDEM-01` ainda diz «pad
  degradado»; `scripts/bancada_do_radio.py:18-26` chama o `poll.tick` de
  instrumento do dano.

## 8. A autoria no versionado (eixo 08, cinco altos)

A política de autoria do repositório original (o bloco do `.gitignore`, o
`scripts/check_anonymity.sh`, o `anonymity-check.yml`) **fica** — o
`git blame` a atribui ao mantenedor. O que o eixo achou:

- A história de antes da reescrita de 15/09 ainda é servida pelo GitHub por
  SHA: 30 de 30 commits respondem nos dois repositórios públicos.
- Nove PRs antigos e quinze notas de release carregam rastro de ferramenta; o
  `CHANGELOG.md`, que o `release.yml:395-425` publica como nota, é isento do
  portão (`scripts/check_anonymity.sh:53`).
- O pacote carrega o rastro: o wheel v0.9.4.5 publicado, 86 linhas de `src/`
  em 47 arquivos, as páginas 02 e 04 (vindas de `aba02.py:1981,3087` e
  `aba04.py:1004`), o AppStream, o `.spec` e o `.desktop`.
- Os portões são cegos a famílias que existem, e o vocabulário tem **cinco
  donos divergentes**. Na árvore: 560 linhas em 233 arquivos a limpar.
- `scripts/ensaios/o_touchpad_chega_na_tela_de_baixo.py:112` importa um módulo
  ignorado pelo `.gitignore` e morre com `ModuleNotFoundError` em qualquer
  clone.

Proposta: um dono único do vocabulário e um portão com modos de árvore,
mensagem, intervalo e artefato, ancorado num marco de SHA; limpar primeiro o
que vai no pacote, depois o resto. Para a história: H0 (não reescrever, limpar
o GitHub, marco no portão), H1 (reescrever mensagens), H2 (conteúdo também) ou
H3 (história nova). A recomendação foi H0; reescrever muda 3.869 dos 3.910
commits do `dev` e as 62 tags. **Nenhum release antes do pacote limpo** (a
síntese ficou com o eixo 08 contra o 09).

## 9. Pronto para o mundo (eixo 09, seis altos)

- **Quem chega instala o produto de agosto.** `README.md:101-106` e
  `docs/usage/quickstart.md` mandam `git checkout v0.9.4.5` — a janela GTK
  que saiu em 06/09, 3.160 commits atrás. Proposta: retomar a série 0.9.x.x e
  cortar a 0.9.4.6 com o CI verde.
- **Nenhum release é possível**: `release.yml:303-368` exige o CI verde, que
  não existe desde 22/08.
- **A interface é dependência dura e ninguém a declara.** O lançador faz
  `require_version('WebKit2','4.1')` (`hefesto_vivo.py:26`), o `install.sh:793`
  a chama de «importante» com razão falsa, e nenhum dos pacotes (Debian, Arch,
  Fedora, Nix) a lista. O AppImage publicado é só a linha de comando.
- **O que é da bancada vai para toda máquina**: o DKMS rtw88 (com
  `BUILD_EXCLUSIVE_KERNEL` pinado em dois kernels), o vigia do Wi-Fi USB e o
  `usbcore.autosuspend=-1` global (`install.sh:2430-2442`), sem detectar
  hardware.
- O arquivo de contrato da casa, que é ignorado pelo git, é citado 113 vezes
  em 61 arquivos versionados, e o portão isenta o nome.
- **A porta de quem chega descreve outro produto**: o quickstart fala das onze
  abas, o README tem cinco afirmações vencidas, e nenhum texto público diz
  «acessibilidade».

Médios: o backport do BlueZ trava as atualizações de segurança da distro (o
apt nunca aplica, sobre a 5.86 da casa, a 5.72 que a distro publica em
`noble-updates`), e o `scripts/doctor.sh:4741` dá FAIL e manda compilar; o
`.deb` não instala o broker e o Flatpak usa o runtime GNOME 47, fora de
suporte; nenhuma distro imutável é reconhecida e a
matriz do CI tem Fedora 40; o uninstall deixa 1,1 GB de tarballs do Proton e o
Steam Input desligado; a primeira instalação baixa 537 MB sem Steam, instala
os extras `[dev]` e descarta o stderr do pip; o broker serve um uid só
(`assets/systemd/hefesto-hidraw-broker.service:37`); 67 links versionados
apontam para uma pasta fora do git.

## 10. As sprints de 27/09 e o que fechou em 26/09 (eixos 01 e 02)

- **O CI voltou a reprovar num hook que os portões não rodam.** A corrida do
  `d587a737f` caiu no `pre-commit`, no `indice-html-publicado`: dos 13 hooks
  do `.pre-commit-config.yaml`, é o único sem espelho no `scripts/portoes.sh`.
- **A camada Freestyle, como escrita, ligaria a emulação de mouse, inverteria
  a mira e mataria o giroscópio.** «Liga todo liga/desliga» e «no máximo todo
  campo de intensidade» alcançam `profiles/schema.py:331`, `:524-525` e `:528`
  (zona morta de 60 °/s). Proposta: uma tabela de classes fechada, em que
  «camada» vale só para as features.
- **O tique da 08 em cartões pesa no fio da janela**: depois da cura do
  Mapear, 88 tiques lentos, de 104 a 714 ms (mediana 343 ms), com IPC 0 ms,
  contra o teto de 100 ms; a 09 paga de 0,9 a 2 s na primeira pintura.
- **«Perfil Máximo» e «Personalizado» dão o mesmo aparelho**
  (`app/actions/config/secao_orcamento.py:202-206` grava `None` e `False`, e
  `profiles/schema.py:1503-1510` trata os dois igual). Texto novo na dica não
  é cura.
- **O nome dado ao controle só existe pelo Alias do BlueZ**
  (`interface/pacotes/a08_conexoes.py:5050-5072`): no cabo sem pareamento, ou
  numa máquina sem Bluetooth, o controle fica em «P N».
- **A partida da háptica zera marcas no meio do jogo** (o `isdisjoint` de
  `quem_mexe.py:122`): às 05h07 de 27/09, as quatro marcas do Sackboy foram
  zeradas sem fechamento.
- **Fato errado em quatro lugares.** A frente USB da placa da bancada é 2.0
  elétrica; quem engana é o *peer* das duas pretas de trás. A razão «a frente
  é USB 3.0 e a placa erra» está em `integrations/mapa_das_portas.py:527-533`,
  `interface/pacotes/a12_mapa_das_portas.py:12-13`,
  `tests/unit/test_a_entrada_declarada_vence_o_firmware.py:3-8` e na
  `D-2609-A-VELOCIDADE-DECLARADA-VENCE-O-FIRMWARE`.

## Conflitos que a síntese decidiu

- A háptica no USB vale `sim` no mapa, pelo device KS: a coluna pergunta «o
  Hefesto aciona?».
- As variáveis de ambiente da ferramenta estão só num comentário
  (`reposicao_dos_lancadores.py:24`), não no `fora_do_servico.py`.
- Três outras decisões já estão acima: o bloco do `.gitignore` fica e nenhum
  release sai antes do pacote limpo (seção 8); o buraco na entrada ainda não
  tem dono provado (seção 5).

## O que ficou aberto

- **Da palavra dela:** se o Xbox das 01h34 foi de propósito; a escolha (a) ou
  (b) da háptica pelo rádio; o que o «Perfil Máximo» faz; se a economia vale
  no USB (a recomendação é que não); onde mora o mudo do microfone; o caminho
  de volta do «Remover» na tela; PS + R3 e o PS sozinho nos quatro controles;
  o preço de fidelidade do giroscópio se a taxa do virtual cair.
- **Da palavra dela e do mantenedor, numa pergunta só:** H0, H1 ou H3 para a
  história publicada, juntando a narrativa e o endereço. O pedido de expurgo
  ao suporte do GitHub é do mantenedor no repositório original, e dela no
  fork.
- **Sem medida ainda:** o dono do buraco na entrada dos virtuais; o custo do
  xalia e da taxa de 250 Hz no wineserver; o par modo Xbox + máscara DualSense
  num jogo; a causa exata dos 300 a 700 ms do tique da 08 (mediana 343 ms
  contra o teto de 100 ms); o som codificado e a háptica juntos no mesmo
  0x35; o efeito do broker num segundo usuário.
- **Sprints a corrigir antes de despachar:** a do Salvar (causa 3, item 6,
  prova 2), a do Freestyle (partir em duas, com a posse inteira), a
  `A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01` (partir em 8a e 8b, com a
  coluna «microfone fechado»), a da háptica (o critério por arranjo: canais
  3-4 no modo háptica, 1-2 no modo som), a do engasgo (ensaios reescritos) e
  as duas de CI (as datas).
- **Sprints novas nomeadas pela auditoria**, entre outras:
  `O-MODO-XBOX-NAO-E-QUEDA-02`, `O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01`,
  `A-TROCA-DE-CONTROLE-NAO-PARA-O-LACO-01`, `O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01`,
  `O-GESTO-DE-CAMPO-NAO-ATIVA-O-PERFIL-01`, `O-DESTINO-DA-GRAVACAO-TEM-UM-DONO-01`,
  `A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01`, `O-BASICO-MEDIDO-01`,
  `TODO-GESTO-SE-ALCANCA-SEM-MOUSE-01`, `A-JANELA-SE-NAVEGA-PELO-CONTROLE-01`,
  `A-RECUSA-SE-ENTENDE-SEM-COR-01`, `O-TIQUE-DE-CADA-ABA-CABE-NO-TETO-01`,
  `A-TELA-E-DEPENDENCIA-DURA-01`, `O-QUE-E-DA-BANCADA-FICA-NA-BANCADA-01` e
  `A-PORTA-DE-QUEM-CHEGA-01`.
