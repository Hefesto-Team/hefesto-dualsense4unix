# O porquê dos módulos

A docstring de um módulo diz o CONTRATO: o que ele faz, por que, e para onde olhar. A história da
decisão (a medição, a auditoria, o fato substituído, a citação dela) mora aqui e nos documentos de
tema. Cada seção abaixo guarda, sem corte, o que a docstring dizia antes de virar contrato em
13/10/2026 (A-DOCSTRING-DIZ-O-CONTRATO-E-A-HISTORIA-MORA-NO-DOCUMENTO-01). O que lá se chama «aqui
embaixo» ou «acima» fala do arquivo de origem.

Quem for acrescentar história a um módulo acrescenta aqui, na seção dele, e mantém a docstring
curta: a catraca `scripts/check_docstring_longa.py` só deixa o total de linhas em docstrings de mais
de dez linhas descer.

Seções: [identity](#identity), [nivel_do_microfone](#nivel_do_microfone), [dualsense_bt_audio](#dualsense_bt_audio), [external_mask](#external_mask), [bt_mic](#bt_mic), [ControllerOverrides](#controlleroverrides).

## identity

`src/hefesto_dualsense4unix/daemon/subsystems/identity.py (docstring do módulo)`. O "Controle N" estável de cada DualSense: o lugar do MAC na fila de preferência.

~~~~text
Registro de identidade MAC→posição na mesa (COR-01, sprint cores-e-led).

O "Controle N" que a usuária vê (rótulos, cor automática da lightbar, LED do
número do controle) era a POSIÇÃO no dict de handles do backend (+1) — replug
reinsere no fim e o número embaralhava. Este registro dá a cada DualSense um
lugar ESTÁVEL na fila, keyed pelo MAC normalizado (12 hex — o mesmo
``norm_mac`` do backend, estável entre USB e BT):

- 1ª aparição de um MAC → entra no FIM da ordem de preferência, atribuição
  LAZY na primeira consulta (``slot_for``) — é isto que faz a cor automática
  nascer certa no MESMO tick de hotplug em que o backend abre o handle (D1);
- desconectar mantém o lugar do MAC na fila — replug recupera o mesmo
  número (D2). Sem roubo LRU (cortado: YAGNI);
- R-15 (auditoria 23/07): DENTRO de um boot, número é do MAC e NINGUÉM
  expira. A expiração por "sessão esvaziou" (o ramo ``_saw_connected`` do
  ``sync_connected``) foi REMOVIDA: ela era assimétrica (só o lado
  DualSense expirava; o registro dos externos nunca expirou) e trocava
  cor/número de dono conforme a ORDEM DE WAKE — desligar os dois DualSense
  e religar em ordem invertida devolvia o 1 ao que voltasse primeiro. Pior:
  entre a expiração e a reatribuição, ``_ds_reserve()`` (external_identity)
  lia piso 0 no meio do tick externo e abria janela de DUPLICATA — a queixa
  "dois player 1, dois player 2";
- R-23 (auditoria 25/07): o número TAMBÉM sobrevive ao BOOT. Era aqui que a
  queixa "ao abrir os jogos ou o perfil, os controles se reenumeram e nunca
  sei o que é o quê" nascia: o ``load`` descartava o ``controllers.json``
  inteiro quando o ``boot_id`` do arquivo diferia do da máquina, então TODO
  reboot renumerava por ordem de conexão. Pior em contêiner/Flatpak, onde
  ``/proc/sys/kernel/random/boot_id`` some: sem boot_id o load abortava e
  bastava REINICIAR O DAEMON para renumerar tudo. O mapa é keyed por MAC —
  e MAC não muda no reboot: ele é IDENTIDADE, não sessão. A única
  renumeração automática que sobrou é a de SCHEMA (arquivo gravado por uma
  versão que numerava de outro jeito, ver Persistência); renumerar por
  vontade dela continua sendo o GESTO explícito ("Renumerar agora" →
  ``compact``);
- R-24 (auditoria 25/07): a atribuição deixou de ser SÓ lazy. ``slot_for``
  só é chamado pelo provider de cor (caminho de output); enquanto nenhum
  DualSense tivesse sido consultado, o registro ficava VAZIO e o piso que
  os externos leem (``_ds_reserve``) valia 0 — o Pro Nintendo tomava o slot
  1 no primeiro tick de externo e os DualSense herdavam 2 e 3 (o "não
  existe Controle 1" medido ao vivo). Agora ``sync_connected`` (tick lento,
  que roda ANTES do tick dos externos no mesmo laço do lifecycle) ATRIBUI
  lugar a todo DualSense conectado que ainda não tem — quem está na mesa
  ocupa 1..N antes de qualquer externo pedir número;
- NUM-01 (25/07): **o que se persiste deixa de ser um número absoluto**.
  R-15 e R-23 curaram a instabilidade ("cor e número trocavam de dono")
  prendendo o NÚMERO ao endereço para sempre; o preço apareceu medido no
  ``controllers.json`` dela: com um só DualSense ligado, ele exibia 2 —
  porque o 1 estava RESERVADO a um endereço que não estava na mesa
  ("ninguém aceita ser o jogador 2 de si mesmo"). Os dois requisitos são
  verdadeiros ao mesmo tempo, e a saída é separar os dois conceitos que
  eram o MESMO inteiro:

  - IDENTIDADE é o endereço, e o que fica gravado dele é o LUGAR NA FILA
    (a ordem de preferência: A vem antes de B) — permanente, estável entre
    sessões e entre boots, exatamente como R-15/R-23 exigem;
  - POSIÇÃO NA MESA é 1..N entre QUEM ESTÁ PRESENTE AGORA — derivada a cada
    consulta (``slot_for``), nunca persistida como número.

  Com os dois na mesa, a fila ``[A, B]`` dá A=1 e B=2 (estabilidade); com só
  o B ligado, a MESMA fila dá B=1 (naturalidade), e quando A volta cada um
  recupera o seu. Fechar a lacuna deixa de ser um gesto e passa a ser
  aritmética. O critério que resume: **nunca existe um jogador 2 sem um
  jogador 1**;
- **D-30 / ORDEM-DE-CHEGADA-01 (decisão, 15/08/2026, 03:54)**: o número
  segue a **ordem de conexão daquele momento**, e não mais o lugar que o
  endereço ganhou num dia qualquer do passado — *"deve ser lembrado por ordem
  de conexão naquele momento apenas. Não uma imagem fixa salva por mec"*. Isto
  REVERTE em parte R-15 e R-23, e por isso vem com as duas garantias que
  aquelas auditorias compraram, escritas aqui como invariante:

  - a **FILA DO MOMENTO** (``_chegada``) é o que ordena a exibição. Ela
    guarda, por key, a **ONDA** em que a casa VIU aquele controle chegar
    (:data:`JANELA_DE_ONDA_SEC`) — não um carimbo de relógio de parede, e
    nada disso vai para o disco;
  - **empate de onda desempata pelo GRAVADO** (o ``rank``). Dois controles
    vistos na MESMA olhada para a mesa (o mesmo ``sync_connected``, o mesmo
    tick do provider) chegaram, para a casa, ao mesmo tempo: aí o registro
    NÃO inventa uma ordem, ele lê a que já tinha. É este degrau que faz o
    restart do daemon com quatro controles já ligados não embaralhar nada
    (R-23) — quem sobrevive ao restart é o gravado, e é dele que a ordem
    renasce;
  - **a marca de chegada NUNCA é solta dentro da sessão** — quem cai e volta
    recupera a onda que tinha, e portanto o MESMO número (D2/R-15). É a
    diferença entre esta entrega e a renumeração por ORDEM DE WAKE que R-15
    arrancou em 23/07: lá, religar dois controles em ordem invertida trocava
    o dono do 1; aqui, os dois voltam ao que eram porque a onda deles é a de
    quando chegaram, não a de quando voltaram;
  - **CONGELAR é gravar** (:meth:`_congelar_locked`): quando a mesa fica
    :data:`JANELA_MESA_ESTAVEL_SEC` sem entrar nem sair ninguém, a ordem do
    momento é escrita na FILA GRAVADA — os ``rank`` dos PRESENTES são
    permutados entre si, na ordem de chegada. O conjunto de ``rank`` não
    muda, só o dono de cada um: nenhum posto some, nenhum vale 0 no meio do
    caminho, e por isso a janela de DUPLICATA que R-15 mediu
    (``_ds_reserve`` lendo piso 0) não pode reabrir. Depois de congelada, a
    ordem do momento e a gravada dizem a MESMA coisa — e é a gravada que
    atravessa o restart e o reboot, exatamente como R-23 exige.

  O que continua valendo de R-15/R-23, sem asterisco: nada expira, o lugar
  do ausente não é dropado, e o "Renumerar agora" (``compact``) segue sendo
  o gesto explícito dela;
.. note::

   **"D9" AQUI NÃO É O "D9" DO DESENHO.** Neste módulo ``D9`` é a decisão do
   *slot volátil* (abaixo). Em
   o registro «O-QUE-ELA-DESENHOU-o-todo-por-aba» de 26/08/2026 ``D9`` é
   outra coisa — a decisão dos três botões de sensor na aba Controles. Os dois
   documentos estão entre os primeiros que quem chega abre, e a colisão já
   custa uma busca errada por leitura; registrada em 29/08/2026 para não custar
   duas.

- o vpad (MAC forjado ``02:fe:...``) NUNCA ganha slot (D9) — o filtro
  existe aqui além do filtro de enumeração do backend, porque outros
  chamadores (describe/co-op) também consultam;
- key sem MAC 12-hex (fallback ``path:...`` de firmware sem serial) ganha
  slot VOLÁTIL: vale na sessão, nunca é persistido (D9 — path muda entre
  boots).

  **O QUE ISSO CUSTA A UM USUÁRIO, escrito em 29/08/2026 porque a mesa desta
  casa NÃO TEM COMO REVELAR:** para quem tem um controle sem serial de 12 hex,
  a memória por identidade **não funciona nunca** — nem os LEDs, nem os
  gatilhos, nem a vibração, nem o alto-falante voltam como ele deixou, em jogo
  nenhum, em sessão nenhuma. Não é degradação: é o recurso inteiro ausente, em
  silêncio, sem uma linha na tela dizendo por quê. Os cinco controles desta
  bancada têm MAC de 12 hex, então **toda prova feita aqui passa** — é a
  amostra mais favorável possível, e é exatamente o que a
  ``D-A-REGUA-E-QUALQUER-MESA-NAO-A-DELA`` (decisão, 29/08/2026) condena. Dono:
  ``O-CONTROLE-SEM-MAC-01``.

  A decisão de não persistir continua CERTA — um path que muda entre boots
  persistido é pior que nada, porque devolve a configuração de um aparelho a
  outro. O que falta não é gravar o path: é uma chave estável para quem não tem
  MAC, e é isso que a sprint procura;

- **O SEGUNDO CONDUÍTE (O-CONTROLE-SEM-MAC-01, 06/09/2026).** A key deixou de
  cair DIRETO no volátil: quando o serial falta, o registro pergunta ao
  ``cracha_provider`` (:meth:`ControllerIdentityRegistry.set_cracha_provider`),
  e só desiste depois dele — e a desistência passou a ser ANUNCIADA
  (:data:`FRASE_SEM_CRACHA`, :meth:`avisos_sem_cracha`).

  **A FORMA DA CHAVE NOVA É A FORMA DA CHAVE VELHA: 12 hex canônicos**, e isso
  não é economia de código, é o requisito. O que o crachá devolve é o MESMO
  endereço que o serial devolveria — outra estrada para o mesmo valor —, então
  o perfil, o ``sysfs_leds``, o co-op e o disco não aprendem forma nenhuma.
  Quem vem depois (``QUEM-E-QUEM-04``) abre a porta do perfil para uma forma
  que já existe.

  **QUAL crachá, e por que não os cinco.** O ensaio de 15/08 achou cinco
  candidatos que saem nos dois transportes e são estáveis byte a byte
  (``0x05``, ``0x09``, ``0x0b``, ``0x20``, ``0x22``); a MESMA linha do mapa
  (``docs/data/mapa-controles.csv``, ``identidade.cracha_nos_dois_transportes``,
  célula ``cabo_detalhe``) já dizia que quatro deles **só pareciam servir**: o
  ``0x20`` agrupa por REVISÃO DE PLACA (a data de compilação colide em PARES
  nos quatro controles desta casa), o ``0x05`` é calibração de IMU e é
  REESCRIVÍVEL pela família ``0x80``, e o ``0x22`` só distingue porque EMBUTE o
  endereço (``buf[17..22]``). Sobra o ``0x09`` — ``buf[1..6]``, o endereço
  invertido —, que é de onde o próprio ``hid_playstation`` tira o ``HID_UNIQ``.
  Por isso o provider devolve **um endereço**, não "um crachá": as duas
  estradas honestas (``0x09`` e o ``0x22`` que o embute) chegam ao mesmo valor,
  e as outras duas não são identidade de unidade.

  **Este módulo não fala com o aparelho, e não vai passar a falar.** Ler
  ``0x09`` é I/O de hidraw, e a docstring da classe promete um ``slot_for`` sem
  I/O (ele roda sob o ``_io_lock`` do backend). O provider é seam: quem sabe
  ler o aparelho é o backend; aqui só se guarda o que ele respondeu. A pergunta
  acontece no TICK LENTO (``sync_connected``, ~2 s, fora do lock) e o caminho
  quente lê só o cache;

- **o crachá NUNCA vence o serial.** Se a key já é um MAC 12-hex, o provider
  não é nem consultado — trocar a chave de quem já é lembrado apagaria a
  memória de toda mesa que hoje funciona, que é exatamente o estrago que esta
  frente existe para evitar;

- **o cache do crachá é esquecido na saída.** Ele é indexado pelo ``uniq``
  CRU (o path), e um path volta a circular: ``/dev/hidraw3`` liberado pode ser
  reocupado por OUTRO aparelho na mesma sessão. Guardar o crachá do primeiro
  não interromperia a identificação — CORROMPERIA, que é pior, e é o único
  desfecho que a ressalva do mapa exclui (*"trocar de braço, cair o rádio ou
  desligar o controle INTERROMPEM a identificação — não a corrompem"*). Então
  quem sai da mesa perde o cache, e volta perguntando de novo;
- DualSense-only (D10) é garantido pelo CHAMADOR por construção: os uniqs
  que chegam aqui vêm dos handles físicos do backend (a enumeração filtra
  por VID/PID da Sony e descarta hidraw virtual). O registro não conhece
  hardware — só strings.

Separação D3 (Refutado 2 do sprint): este slot é EXIBIÇÃO/LED. O índice de
alocação do vpad do co-op (``_next_player_index`` + ``player=1`` do
primário) fica intacto. O MAC do vpad só sai dele sem identidade de aparelho
(E3), e dois vivos nunca o repetem (``uhid_gamepad._MacsDosVpadsVivos``,
O-VPAD-DO-P1-NAO-REPETE-O-MAC-01). R-24 precisou o limite: o índice do vpad é
do JOGO (contíguo, reusado quando alguém sai) e o slot daqui é da EXIBIÇÃO; o
defeito era a LÂMPADA acender o primeiro. Hoje ``CoopManager._numero_exibido``
lê ESTE registro para a barra de player e o índice do vpad nunca chega a um LED.

Persistência (``controllers.json`` no config do app, escrita atômica
mkstemp+os.replace — padrão ``utils/session.py``): cobre o restart do daemon
E o reboot da máquina (R-23). O que governa o load é o
:data:`CONTROLLERS_SCHEMA_VERSION` do arquivo, não mais o ``boot_id``:

- versão IGUAL → a ORDEM DE PREFERÊNCIA (campo :data:`ORDER_FIELD`) é
  restaurada INTEIRA. Entradas voláteis (sem MAC 12-hex) nunca chegam ao
  disco (D9), então "descartar o volátil" é invariante do save, não
  trabalho do load;
- versão DIFERENTE/ausente → arquivo escrito por uma versão que numerava
  por outra regra; é descartado UMA vez e a sessão seguinte renumera. É o
  que cura, sozinha, a numeração torta já gravada na máquina do usuário (o
  externo segurando o slot 1 enquanto os dois DualSense exibiam 2 e 3, e
  depois o ``{"a0fa…": 1, "143a…": 2}`` que fazia o controle sozinho na
  mesa nascer jogador 2 — NUM-01);
- o ``boot_id`` continua GRAVADO, agora como âncora de diagnóstico
  (:func:`_session_anchor`, resiliente: boot_id → machine-id → ``None``).
  Ele não pode mais decidir nada sozinho — foi exatamente a fragilidade
  que renumerava tudo onde ``/proc/sys/kernel/random/boot_id`` não existe.

NUM-01: o arquivo tem UMA fila só, não duas paralelas. O campo
:data:`ORDER_FIELD` é uma LISTA ordenada de ``{"addr", "kind", "rank"}``
onde ``kind`` diz de qual registro é a entrada (:data:`KIND_DUALSENSE` /
:data:`KIND_EXTERNAL`) e ``rank`` é o lugar na fila GLOBAL — os dois lados
dividem um espaço de postos único (era esse compartilhamento que os campos
``slots``/``externals`` do schema 2 escondiam, e é dele que sai a garantia
de nunca haver dois "Controle 1"). Cada save é read-modify-write: preserva
as entradas do OUTRO ``kind`` byte a byte (:func:`merged_order_payload`) e
reescreve só as suas. O ``rank`` é GRAVADO, nunca inferido da posição na
lista: se cada save recompactasse os postos, o lado que não salvou ficaria
com valores obsoletos e a ordem RELATIVA entre um DualSense e um externo
podia inverter sozinha entre dois saves.

O ``config_dir`` é importado LAZY dentro das funções de I/O — preserva
o ponto de monkeypatch dos testes (``xdg_paths.config_dir``), padrão
``save_active_marker``. O arquivo é COMPARTILHADO com o registro dos
externos (``external_identity.py``): ``load`` e ``_save_locked`` dos DOIS
lados adquirem o mesmo ``CONTROLLERS_FILE_LOCK`` (NUMA-04) em volta do
read→``os.replace`` — fecha o lost-update dos dois escritores
independentes sem unificar os dois registros.

Hierarquia de locks (NUM-01 tornou-a explícita porque agora há travessia
nos DOIS sentidos): ``ControllerIdentityRegistry._lock`` → ``External
IdentityRegistry._lock`` → ``CONTROLLERS_FILE_LOCK``. Este registro CHAMA
os providers do lado externo segurando o próprio lock (``_assign_locked``,
``_posicao_locked``); o lado externo, por isso, é PROIBIDO de consultar
este registro segurando o dele — ``ExternalIdentityRegistry`` resolve o que
precisa daqui ANTES de adquirir o próprio ``_lock``. Inverter isso fecha um
ciclo com o ``identity.renumber``, que toma os dois na ordem canônica.

Config do automático (COR-03): o registro também guarda o estado vigente do
toggle ``auto_player_colors`` e do brilho do perfil ativo (D11), configurados
pelo ``ProfileManager.apply`` a cada ativação e consultados pelo provider de
cor injetado no backend (``make_auto_output_provider``).

R-14 (auditoria 23/07) — o automático são DUAS coisas, não uma:

- **ATRIBUIÇÃO de slot** (quem é o Controle N) acontece SEMPRE, com o
  automático ligado ou desligado. Antes, o provider fazia o early-return do
  flag ANTES de ``slot_for`` e o DualSense simplesmente não ganhava número
  enquanto o perfil tivesse ``auto_player_colors:false`` (o ``fps.json``
  dela) — sem número no registro, o piso dos externos (``_ds_reserve``)
  também mentia e a numeração global congelava. Atribuir é identidade;
  desligar o automático é uma opinião sobre APARÊNCIA.
- **APARÊNCIA** tem dois eixos independentes: ``auto_colors`` (a paleta da
  lightbar) e ``auto_numbers`` (o padrão de player-LED do NÚMERO do
  controle, e o LED de número dos externos). Eram o MESMO flag, então um
  clique de cor na GUI apagava a numeração de todo mundo — inclusive a dos
  externos. ``configure(enabled=…)`` mapeia o campo ANTIGO do perfil
  (``auto_player_colors``) para o eixo COR apenas; ``auto_numbers`` nasce
  ``True`` e só muda por ``configure(numbers=…)``. É a migração de default
  compatível: perfil salvo com ``auto_player_colors:false`` perde a paleta,
  nunca a numeração.
~~~~

## nivel_do_microfone

`src/hefesto_dualsense4unix/integrations/nivel_do_microfone.py (docstring do módulo)`. O medidor da luz do mic: está entrando som neste microfone agora?

~~~~text
Está entrando som NESTE microfone agora? — o medidor da luz do mic.

LUZ-DO-MIC-01, PEÇA B (03/09/2026). Esta peça responde UMA pergunta, por
controle: *está entrando som neste microfone agora?* Quem decide a luz é a
PEÇA C (`daemon/subsystems/luz_do_mic.py`); quem diz se **alguém está ouvindo**
é a PEÇA A (`integrations/quem_ouve_o_microfone.py`). Aqui só se mede.

O CONTRATO DE SAÍDA são três valores, e a diferença entre dois deles é o
coração da peça:

* ``True``  — medi, e está entrando som.
* ``False`` — medi, e não está.
* ``None``  — **não sei**. Sem canal para este controle (o do rádio não publica
  nenhum), sem ``parec`` na máquina, fluxo recém-aberto que ainda não entregou
  amostra, ou fluxo vivo que parou de entregar. ``None`` NUNCA vira ``False``:
  ``False`` diz "medi e não há som", e a luz apagaria mentindo.

## O CAMINHO, e por que é este

O pico é calculado **pelo servidor**, não por nós. O PipeWire não publica nível
de sinal por propriedade nenhuma — medido 03/09 no ``pw-dump`` inteiro, as
únicas chaves que casam com ``peak|level|rms`` são ``resample.peaks`` (um
BOTÃO, não um valor), ``linking.role-based.duck-level``, ``log.level`` e
``nice.level``: nenhuma é nível de sinal. Mas esse botão existe, e é o caminho:
``resample.peaks=true`` troca a reamostragem por ``max|x|`` do bloco. A 25 Hz o
cliente recebe 25 float32 por segundo, ou seja **100 bytes/s por canal, já
mastigados**. Do nosso lado sobra um ``struct.unpack`` de quatro bytes.

**Zero dependência nova**, e isso é requisito da PEÇA E: o ``parec`` sai do
MESMO pacote que o ``pactl`` (``pulseaudio-utils``), que o ``install.sh:504``
já declara para as três famílias. Do lado Python é só a biblioteca padrão —
o ``numpy`` NÃO está no ``pyproject.toml`` (vive no ``~/.local`` dela), e
importá-lo repetiria a dívida do ``playwright``, que ``test_o_install_entrega_a_luz_do_mic`` cobra.

**O modo de pico entrega o pico VERDADEIRO, e isto é medida, não confiança.**
20 s com DOIS fluxos abertos na MESMA fonte do DualSense ao mesmo tempo: o
nosso, a 25 Hz com ``resample.peaks``, deu ``max = 0,013535`` (-37,37 dBFS) em
500 amostras; uma captura CRUA de 48 kHz ao lado, verdade de campo, deu
``max = 0,013550`` (-37,36 dBFS) em 960.000 amostras. A razão entre os dois é
**0,9989** — os dois máximos distam 0,01 dB, meio passo de quantização do s16
que a captura crua usa. **Mesmo pico, com 1/960 do tráfego** (100 B/s contra
96.000 B/s).

Medido em 03/09/2026, e cada linha é uma decisão:

* ``--property=resample.peaks=true`` no argv LIGA o modo de pico — provado pela
  mordida, na MESMA fonte e no mesmo minuto: com a propriedade, ``max =
  0,013535``; sem ela, ``max = 0,000245`` (-72,2 dBFS), **55 vezes menor** e
  vinte e cinco vezes abaixo do limiar de entrada. Sem a propriedade a luz
  nunca piscaria, e o defeito seria silencioso: o fluxo abre, as amostras
  chegam, e todas dizem "silêncio".
* ``--latency-msec=100`` **não é opcional**. Com o fragmento padrão a primeira
  amostra do ``parec`` chega aos **2,006 s** (e ``stdbuf`` não resolve); com a
  flag, aos 96 ms (mediana de cinco corridas). Sem ela o medidor mede o passado
  e a luz pisca fora do tempo.

## O CUSTO, medido com ESTE módulo, por QUATRO réguas independentes

Régua: CPU por processo lida em ``/proc/<pid>/stat`` (utime+stime), janela de
30 a 40 s **descartando a partida** — o custo aparente de 18 % da primeira
corrida do levantamento era PARTIDA, não regime. Somam-se o Python deste
módulo, os ``parec`` filhos e os deltas de ``pipewire``, ``pipewire-pulse`` e
``wireplumber``. Percentuais são de **UM** núcleo; a máquina do usuário tem 16.

.. _custo-medido:

=================  ==========  ==========  ==========  ==========
canais medindo     corrida A   corrida B   corrida C   corrida D
=================  ==========  ==========  ==========  ==========
0 (piso)           0,000 %     0,000 %     0,000 %     0,000 %
1                  0,109 %     0,125 %     0,153 %     0,300 %
4                  0,325 %     0,350 %     0,357 %     0,400 %
=================  ==========  ==========  ==========  ==========

**QUATRO canais custam entre 0,33 % e 0,40 % de UM núcleo — no pior caso
0,025 % das 16 linhas dela.** É esse o número que decide, porque a mesa é de
quatro, e ele é estável: quatro medições feitas por réguas escritas
separadamente caem numa faixa de 0,08 pontos percentuais.

O de UM canal é ruidoso de propósito (0,11 a 0,30 %) e não deve ser citado
sozinho: ele mora no chão do instrumento. O ``/proc`` conta em tiques de 10 ms,
o que dá ±0,025 pontos percentuais numa janela de 40 s, e a máquina tinha
outros processos trabalhando (``loadavg`` entre 1,2 e 2,4 durante as corridas).

O custo NÃO cresce quatro vezes — o marginal do 2º ao 4º canal é pequeno,
porque os quatro compartilham o mesmo servidor de som e o mesmo ``epoll``.

**O DEGRAU MENOR VEIO COMO DESENHO, não como recuo.** Este módulo só abre
fluxo para os ``uniq`` que :meth:`NivelDoMicrofone.seguir` receber — e o
chamador (PEÇA C) passa só os controles que a PEÇA A já disse ter ouvinte. É a
precedência da §1.1 da sprint escrita em código: o estado 2 (piscando) só pode
existir dentro do estado 1 (aceso). Na bancada, com ninguém ouvindo, o custo
desta peça é **zero processo e zero por cento** — nada é aberto.

Amostrar por JANELAS curtas foi medido e REJEITADO: a partida é barata (45 a
280 ms), mas abrir e fechar a 0,2 Hz faz o nó piscar entre ``RUNNING`` e
``SUSPENDED``, e é exatamente esse grafo que a PEÇA A lê — o medidor passaria a
tremer a leitura da outra peça, e a ligar e desligar o isócrono USB o dia
inteiro.

## A HISTERESE, e por que ela tem TRÊS degraus

Sem histerese o pisca vira estroboscópio a cada sílaba. Mas o defeito tem uma
segunda porta, e ela custou o número desta seção: **a luz também acende
sozinha, com a sala vazia.** É o mesmo estroboscópio pelo avesso.

**A MEDIÇÃO QUE MANDOU AQUI:** 605 s (15.120 amostras) do mic do DualSense pelo
cabo, sala como ela deixou, ninguém falando.

=======  ==========  ==========
quantil  linear      dBFS
=======  ==========  ==========
p50      0,008713    -41,20
p90      0,011978    -38,43
p99      0,017502    -35,14
p99,9    0,041824    -27,57
p100     0,225800    -12,93
=======  ==========  ==========

O p100 é o número que decide, e ele **não é piso**: só 19 das 15.120 amostras
passam de -30 dBFS (0,126 %). São IMPULSOS isolados — um clique, uma tecla, o
tique de uma ventoinha —, cada um durando uma amostra de 40 ms. O piso
propriamente dito está lá embaixo, no p90 de -38,4 dBFS.

**Por isso subir só a amplitude é a cura errada**, e a grade mede o porquê:
mesmo a -18 dBFS a luz ainda acende sozinha duas vezes em 605 s, e a essa
altura ela já perdeu a fala. O que separa impulso de fala não é altura, é
DURAÇÃO. Daí o terceiro degrau:

* **Amplitude para entrar** — :data:`LIMIAR_ENTRA` (-24,0 dBFS). Deixa 11 dB de
  folga sobre o p99 do piso.
* **Duração para entrar** — :data:`ENTRA_S` (120 ms). O pico tem de ficar acima
  do limiar de entrada por 120 ms CONTÍNUOS, ou seja quatro amostras seguidas a
  25 Hz. Um impulso de uma amostra não passa; uma sílaba passa.
* **Amplitude e tempo para sair** — abaixo de :data:`LIMIAR_SAI` (-30,0 dBFS)
  por :data:`SEGURA_S` (0,6 s) contínuos. A pausa entre duas sílabas é bem mais
  curta que isto: é o que separa "a luz acompanha a fala" de "a luz acompanha a
  forma de onda".

Acendimentos falsos nos MESMOS 605 s de sala real, por par (entrada, duração):

========  ======  ======  ======  ======  ======
entrada   0 ms    80 ms   120 ms  160 ms  200 ms
========  ======  ======  ======  ======  ======
-30 dBFS  9       2       1       1       0
-28 dBFS  9       1       1       1       0
-26 dBFS  7       1       0       0       0
-24 dBFS  5       0       0       0       0
-22 dBFS  3       0       0       0       0
========  ======  ======  ======  ======  ======

O par que este módulo usa é **-24 dBFS com 120 ms**.

O par escolhido não está na beirada do zero: os quatro vizinhos dele na grade
(-26/120 ms, -22/120 ms, -24/80 ms, -24/160 ms) também são zero. E **o par
anterior deste módulo, -30/-36 dBFS sem degrau de duração, acendia a luz nove
vezes** nesses mesmos 605 s, deixando-a acesa 7,2 s — 1,2 % do tempo, com
ninguém na sala. Aquele número não era piso medido: era o piso de uma janela de
31,7 s, curta demais para conter um impulso.

**Duas réguas independentes chegaram no mesmo -24 dBFS.** O levantamento da
peça mediu cinco janelas espalhadas por ~25 min e recomendou "por volta de -24
dBFS" pela contagem de cruzamentos; esta grade chegou lá pela contagem de
acendimentos com histerese completa. É o padrão desta casa: duas réguas, uma
resposta.

**O QUE CONTINUA NÃO MEDIDO, e é honesto dizer:** a âncora de CIMA. Ninguém
gerou fala na sala dela a esta hora. A escolha de 120 ms sobre 200 ms veio de
um MODELO de fala (sílabas de 160/200/240 ms com pausas de 120 ms, caindo ao
piso entre elas): a 200 ms de duração exigida, sílaba nenhuma de 160 ms acende
a luz em amplitude nenhuma; a 120 ms, uma sílaba de 160 ms acende. O modelo é o
pior caso — fala conectada não cai ao piso dentro de uma palavra —, mas modelo
não é medida. **A palavra final é a bancada com ela**, e é por isso que os
QUATRO valores são parâmetros do construtor, não constantes cravadas no laço.

## A TRAVA DE MORTE — um ``parec`` vazado prende o microfone do usuário

Não é hipótese. Em 03/09, às 00h36, um ``parec`` deste medidor ficou órfão
(``ppid=1``) segurando a fonte do DualSense do usuário em ``RUNNING`` por **39
minutos**, num cgroup que não é unit do Hefesto — um ``systemctl --user stop``
do daemon não o recolheria. Ele foi morto à mão e a fonte voltou a ``IDLE``.

**O que segura o filho é o CANO, e isso foi isolado**, matando o pai com
SIGKILL em quatro desenhos:

===========================  ======================
desenho do ``stdout``        o filho…
===========================  ======================
``/dev/null``, mesma sessão  SOBREVIVE — ``ppid=1``
``/dev/null``, sessão nova   SOBREVIVE — ``ppid=1``
``PIPE``, mesma sessão       morre junto
``PIPE``, sessão nova        morre junto
===========================  ======================

A sessão é irrelevante; o cano é tudo. Com o pai morto, a ponta de leitura
fecha, o próximo write do ``parec`` toma ``SIGPIPE`` e ele cai — e em modo de
pico há write a cada 40 ms, então a janela é curta. **Por isso
:func:`abrir_fluxo` usa ``stdout=subprocess.PIPE`` e mais nada**: mandar essa
saída para arquivo, para ``DEVNULL`` ou para um fd herdado reabre exatamente o
vazamento de 00h36. Há teste que morde isso.

O cano cobre a morte do pai. Ele NÃO cobre um ``parec`` vivo que para de
entregar — esse ficaria de pé, mudo, com o microfone do usuário aberto. Quem cobre é
:data:`MUDEZ_S`: o fluxo que emudece por mais que isso é **fechado**, não só
respondido com ``None``. Soltar o microfone do usuário é obrigação, não zelo.

## A IDENTIDADE — o dono é ESTE arquivo, e a razão é uma junta

Se o nosso próprio medidor contar como ouvinte, a luz acende sozinha e a PEÇA A
mente. Esse defeito **não mora dentro de nenhuma das duas peças**: mora na
junta. As propriedades são constantes daqui (:func:`propriedades_do_medidor`);
o crivo é um só, o da PEÇA A
(:func:`~hefesto_dualsense4unix.integrations.quem_ouve_o_microfone.e_stream_do_hefesto`),
e ele cobre as três marcas abaixo.

Medido em ``pactl list source-outputs`` com o argv de :func:`argv_do_medidor`,
verbatim: ``application.name = "hefesto-medidor-de-nivel"``,
``node.name = "hefesto-medidor-de-nivel"``,
``application.id = "br.dev.hefesto.luz_do_mic"``,
``hefesto.papel = "medidor-de-nivel"``, ``hefesto.uniq = "143a9a0000ab"`` e
``resample.peaks = "true"``.

O crivo da PEÇA A aceita TRÊS marcas, e a ordem não é preferência estética:

1. ``resample.peaks = "true"`` é o **intrínseco**. Um fluxo em modo de pico
   recebe envelope, não áudio — ele estruturalmente não consegue ouvir, seja
   nosso ou de quem for. Sobrevive a qualquer mudança de nome que façamos.
2. ``hefesto.papel = "medidor-de-nivel"`` é o **explícito**.
3. ``application.id`` é o terceiro.

**NÃO se põe ``media.role`` no fluxo.** Medido: com ``media.role=Production`` o
servidor grava ``module-stream-restore.id =
"source-output-by-media-role:production"`` — estado de restauração
COMPARTILHADO com todo fluxo de papel produção, e mexer no volume dele mexeria
no de estranhos. Sem ele o id vira
``source-output-by-application-id:br.dev.hefesto.luz_do_mic``, que é só nosso.

**O QUE ESTE CRIVO NÃO ALCANÇA, e é dívida declarada:** o outro ``parec`` desta
casa. `app/mic_monitor.py:488` (`_abrir_captura`) abre um ``parec`` CRU, que
aparece como ``application.name = "parec"`` — indistinguível do ``parec`` de
qualquer outro programa. Com a janela aberta na aba Status, a PEÇA A vê aquele
fluxo como ouvinte. A cura é de uma linha (acrescentar as mesmas propriedades
ao argv de lá) e o arquivo não é desta peça: fica escrito aqui para ter dono.
~~~~

## dualsense_bt_audio

`src/hefesto_dualsense4unix/integrations/dualsense_bt_audio.py (docstring do módulo)`. O microfone do DualSense por Bluetooth: Opus tunelado em HID.

~~~~text
Microfone do DualSense por BLUETOOTH — Opus tunelado em HID (BT-MIC-01).

Por que este módulo existe
--------------------------
Por USB o microfone do DualSense é um dispositivo de áudio USB comum e o
PipeWire o publica sozinho — é dele que o `app/mic_monitor.py` lê o nível.
Por **Bluetooth não existe fonte de áudio nenhuma**, e a razão não é bug do
BlueZ: o DualSense simplesmente **não implementa A2DP/HFP/HSP**. O SDP dele só
anuncia HID (`0x1124`) e PnP (`0x1200`) — comportamento CORRETO, confirmado
pelo mantenedor do BlueZ (Luiz Von Dentz, bluez/bluez#892: *"Doesn't seem like
it is using A2DP/HFP for audio, so I guess it is transmitted over HID so it
needs a kernel driver that can handle these reports"*). Forçar perfil no BlueZ
(`RegisterProfile`) é fantasia: aquilo registra SDP **local**, não muda o que o
controle fala.

O áudio vai **dentro do HID**, no canal L2CAP de interrupção, como quadros
**Opus**. O `hid-playstation` do kernel não trata esses reports (ele loga
"Unhandled reportID" e segue), então o `hidraw` os entrega intactos — dá para
fazer a ponte inteiramente em espaço de usuário, sem patch de kernel. Este
módulo é essa ponte, e é o primeiro daemon nativo de Linux a fazê-la: as
implementações que existiam do protocolo eram firmware de Pico 2 W
(`awalol/DS5Dongle`, MIT — de onde o protocolo abaixo foi extraído e conferido
byte a byte contra `src/audio.cpp`/`src/main.cpp`/`src/bt.cpp`) e hápticos
(`egormanga/SAxense`).

O protocolo (medido AO VIVO nesta máquina, 2026-07-25, DualSense por BT)
------------------------------------------------------------------------
**Ligar o mic (host → controle).** Output report **0x32**, 142 bytes. O corpo
do 0x32 é uma cadeia TLV de blocos ``[tag|flags][len][valor...]`` — o mesmo
envelope que o `update_state` do DS5Dongle usa para o SetState (tag 0x10) e
que o report 0x39 usa para hápticos (0x12) e alto-falante (0x13/0x16)::

    [0]        = 0x32                 report ID
    [1]        = seq << 4             nibble de sequência (ver "disputa", abaixo)
    [2]        = 0x11 | 0x80          tag 0x11 = AudioControl, bit7 = bloco presente
    [3]        = 1                    tamanho do valor do bloco
    [4]        = 0b011 liga / 0b010 desliga     ← o bit que destrava o mic por BT
    [5..137]   = 0
    [138..141] = CRC-32 little-endian, seed 0xA2 (header HIDP DATA|OUTPUT)

**Ouvir o mic (controle → host).** Input report **0x31**, os mesmos 78 bytes de
sempre. O byte ``[1]`` é seq+flags: bit0 = o pacote traz estado de input
(sticks/botões/IMU), **bit1 = o pacote traz ÁUDIO**. Os dois são exclusivos —
não cabem juntos em 78 bytes, e o firmware alterna::

    [0]      = 0x31
    [1] & 2  = pacote de ÁUDIO (se 0, é o report de input normal do kernel)
    [3..73]  = 71 bytes de Opus: mono, 48 kHz, quadro de 10 ms (480 amostras)
    [74..77] = CRC-32 little-endian, seed 0xA1 (o `PS_INPUT_CRC32_SEED`)

O CRC é o MESMO utilitário que o espelho de motion já usa: `bt_crc32` de
`core/ds_output_report.py`, com `BT_INPUT_CRC_SEED`/`BT_CRC_SEED`. Nada de
reimplementar tabela de CRC aqui.

A disputa do contador de sequência (o risco real de integração)
---------------------------------------------------------------
O `hid-playstation` mantém `ds->output_seq` e o rotaciona a cada report **0x31**
que ELE escreve (rumble, lightbar, gatilhos). Nós escrevemos **0x32**. Essa é a
mitigação de verdade e é estrutural, não sorte: *são report IDs diferentes* —
nunca montamos, tocamos ou renumeramos um 0x31, então o kernel continua dono
absoluto do fluxo dele e o nosso contador vive só neste processo.

Sobra a pergunta de se o FIRMWARE mantém um contador único para os dois IDs. A
evidência diz que não importa: o SDL manda 0 fixo em todo report BT desde
sempre e o controle aceita; e na medição ao vivo desta implementação os nossos
0x32 (seq 1 e 2) foram aceitos com o `hid-playstation` escrevendo 0x31 no mesmo
link, sem perder um único report de input. A segunda linha de defesa é a
PARCIMÔNIA: escrevemos 0x32 só na borda (ligar, desligar, e o re-arme quando o
fluxo de áudio morre) — nunca em regime. Um punhado de writes por sessão não
tem como esfomear o fluxo do kernel, mesmo no pior caso.

O preço do mic: ele divide a banda do rádio com o input
--------------------------------------------------------
Medido ao vivo (2026-07-25, A/B no mesmo controle, 3 s por janela)::

    mic DESLIGADO : input 260.4 Hz   audio   0.0 Hz   total 260.4 Hz
    mic LIGADO    : input 170.5 Hz   audio 106.2 Hz   total 276.7 Hz
    desligado again: input 274.3 Hz  audio   0.0 Hz   total 274.6 Hz

O TOTAL de pacotes por segundo é praticamente o mesmo: o áudio não abre um
canal novo, ele ocupa lugar na mesma fila. Ligar o mic custa ~35% dos reports
de input. 170 Hz segue muito acima do poll de 60 Hz do daemon (jogar não
piora), mas o espelho de motion — que mira 250 Hz — entrega menos janelas de
gyro enquanto o mic está no ar. Por isso a ponte é sempre um gesto explícito da
usuária, nunca algo que sobe sozinho: quem usa gyro aiming precisa saber que
está trocando uma coisa pela outra. E a recuperação é total no desligar (a
terceira linha da medição), o que confirma que o efeito é de banda e não um
estado que fica preso no firmware.

**E DESDE 06/09/2026 ESSE PREÇO SÓ SE PAGA COM ALGUÉM OUVINDO**
(ONDA5-MIC-VIRTUAL-02). Até aqui `iniciar()` mandava o 0x32 de LIGAR
incondicionalmente, e o controle transmitia áudio o tempo todo — ouvido ou não.
Agora o pedido SEGUE o estado da source: `RUNNING` (tem app gravando) liga,
qualquer outro desliga. É a mesma coisa que o canal do CABO faz de graça — ele
nasce `SUSPENDED`, publicado e sem capturar nada —, e era essa assimetria que
obrigava o subsystem a negar o CANAL para evitar a CAPTURA. Ver
:meth:`PonteMicBluetooth._talvez_seguir_a_source`.

O NOME DO NÓ MUDOU, E O DEFEITO ERA O NOME (06/09/2026)
--------------------------------------------------------
A ponte publicava ``hefesto_dualsense_bt_<hex6>`` — o TRANSPORTE no nome do
microfone. Troque o cabo pelo rádio e o microfone daquele controle mudava de
nome; um app que fixou o device o perdia. Ela agora publica o canal por
controle, ``hefesto_mic_<marca>``, pelo dono dele
(:mod:`integrations.canal_do_microfone`) e pela MESMA
:meth:`SourceVirtualPipeWire.escrever` por onde o cabo entrega o PCM dele: um
nó, uma entrada, dois transportes. O nome antigo continua sendo o caminho de
volta para controle sem ``HID_UNIQ`` — ver
:meth:`PonteMicBluetooth._abrir_o_canal_por_controle`.

RESOLVIDO — o gating NÃO era do firmware (BT-MIC-GATING-01, fechado em 10/09/2026)
-----------------------------------------------------------------------------------
**A CAUSA É O `hid-playstation`, e o título desta seção estava errado desde
agosto.** O bit `MicMuted` não oscila porque o firmware reage ao mic ativo: ele
oscila porque **o driver o manda mutar e desmutar**, dezenas de vezes por
segundo, a partir de bordas que ele inventa lendo áudio como botão.

O elo que faltava: um quadro de microfone chega com o **mesmo `reportID`
`0x31`, o mesmo tamanho de 78 bytes e CRC-32 válido** que um report de estado.
Só o bit 1 do byte 1 os separa — e o driver não o consulta
(`assets/dkms/hid-playstation/hid-playstation.c`, o ramo `BUS_BLUETOOTH`).
Então `ds_report->buttons[2]` cai sobre payload Opus, o bit
`DS_BUTTONS2_MIC_MUTE` oscila com ele, e na borda de subida o driver inverte
`ds->mic_muted` e escreve `POWER_SAVE_CONTROL_MIC_MUTE`.

Isso explica, de uma vez, tudo o que esta seção mediu e não sabia juntar:

* **por que só acontece com o mic no ar** — só aí existem quadros de áudio;
* **por que ~100 transições em 6 s e ZERO sem o `0x32`** — é a taxa de bordas
  falsas no payload Opus, e sem mic não há payload;
* **por que os quadros com `MicMuted=True` vêm silenciosos** — o microfone
  está REALMENTE mutado nesses instantes, pelo driver;
* **por que nenhuma das três tentativas resolveu** (bloco AudioControl
  completo, `MicSelect`, `SetState`): as três mexiam no que MANDÁVAMOS, e o
  escritor era outro.

**E O «PRINCIPAL SUSPEITO NÃO TESTADO» REGISTRADO AQUI ESTAVA ERRADO.** A
suspeita era o nosso próprio daemon escrevendo `common[9]` a 60 Hz. Não era: o
`dualsense_output_worker` do driver **não é periódico** — é `work_struct`, e só
a rota do botão MUTE o agenda por rádio. O A/B que esta seção pedia (medir com
o daemon parado) teria dado o mesmo resultado e mandado a próxima pessoa para o
lugar errado.

**A CURA está INSTALADA E MEDIDA** (MIC-NAO-E-BOTAO-01, `patch/0003` do fonte
DKMS desta árvore, entregue pelo `install.sh`): o módulo foi carregado em
10/09/2026 e os dois sintomas sumiram. A régua é
`tests/unit/test_o_quadro_do_microfone_nao_e_botao.py`,
e ela trava as duas metades no MESMO bit — porque a metade em Python já fazia a
guarda certa desde 16/08/2026 (`core/physical_report_reader.INPUT_FLAG_AUDIO`,
do PS-PRESO-01). **A casa sabia a resposta numa linguagem e a esquecia na
outra.**

**O NÚMERO CAIU, e é isto que fecha a seção.** Com o módulo curado carregado, e
o mesmo instrumento na mesma duração::

    ANTES   1231 permanências do bit MicMuted, mediana 6,0 ms, p95 27,0 ms
            (o contador de bordas do daemon subindo ~28/s, sozinho)
    DEPOIS  UMA permanência — o bit PARADO por 152 s, zero bordas no journal

Com o microfone no ar e alguém falando, o veredito foi que o controle não enlouqueceu
e o microfone não desligou.
O que restava provar era a queda do número, e ela caiu.

O que a seção media, e continua valendo como medição  # (noqa-acento: verbo/citação)
-----------------------------------------------------
O microfone FUNCIONA (áudio real, decodificado, gravável), mas com o mic no ar
o firmware declara `MicMuted` (byte 55, bit 2) numa fração grande dos reports
de input, e os quadros de áudio dessa fração vêm silenciosos. Medido nesta
máquina, 6 s por janela::

    MicMuted=False : 405 quadros,  97% não-silenciosos, pico médio 9.1, máx 255
    MicMuted=True  : 767 quadros,  17% não-silenciosos, pico médio 1.1, máx  14

Ou seja: o flag é REAL e o áudio o segue. **O ciclo de trabalho publicado antes
aqui caducou em 07/08/2026** (medido com um desmutador acidental rodando por
baixo — ver ``docs/data/caducos.csv`` e o estudo de 03/08/2026 em
o estudo «a-noite-em-que-o-microfone-do-bluetooth-voltou» de 03/08/2026).
Ainda não há substituto medido; o que fica é a ausência declarada, não um
número novo.

O que já está PROVADO sobre ele:

* **A causa é o nosso próprio pedido de mic**, não um estado prévio. Sem o
  0x32 o flag é estável em False (1183 reports, ZERO transições); com ele,
  ~100 transições em 6 s; ao desligar, volta a False e fica. É uma reação do
  firmware ao mic ativo, não o botão físico de mute (nenhum humano alterna
  20 vezes por segundo).
* **Não é falta de "sustentação" do bloco AudioControl.** Refutado por medição:
  bloco completo (`0b01111111`, len 6, com volumes, buffer e o `packetCounter`
  avançando como no DS5Dongle) a 100 Hz — um bloco por quadro de áudio, a
  cadência exata da referência — deixa o MUDO em 60% contra 68% da borda
  simples. Marginal, e ao custo de 598 escritas contra UMA.
* **Não é o caminho do microfone.** `MicSelect` interno / auto / externo,
  fixado por bloco SetState (tag 0x10) com `MuteControl` zerado e
  `AllowAudioMute`, dá 56% / 59% / 69% de MUDO. Nenhum resolve.

Por isso o código mantém a borda simples (UMA escrita): as alternativas custam
centenas de escritas por segundo disputando o link com o `hid-playstation` e
não compram o problema de volta.

**O «principal suspeito» que esta seção nomeava CAIU em 10/09/2026**, e a
frase fica registrada porque ela custou uma hipótese: *"existe um SEGUNDO
escritor de 0x31 neste device — o próprio daemon do hefesto, que emite output
report a 60 Hz"*. O segundo escritor existe, mas não é o nosso daemon: é o
**kernel**, e ele escreve na borda falsa do botão de mudo. Ver o topo desta
seção.

Enquanto isso, a `EstatisticaMic` expõe `mudo_pct` e o `mic bt` o imprime: dá
para medir a anomalia em um comando, com e sem daemon, sem instrumentar nada.

Invariantes (as mesmas do `app/mic_monitor.py`, pagas com os mesmos incidentes)
-------------------------------------------------------------------------------
* **Nada de busy-loop: o áudio é o relógio.** A thread da ponte fica BLOQUEADA
  num `select`+`read` do hidraw. Cada quadro de 10 ms chega quando o rádio o
  entrega; não existe laço de espera ativa em lugar nenhum (foi um laço desses
  que fez os 104% de CPU da v3.8.1).
* **Nada de subprocess na thread GTK.** `pactl` só roda no start/stop da ponte,
  na thread de quem chamou (CLI/daemon), nunca na interface.
* **Ausência é resposta.** Sem `libopus`, sem `pactl`, sem controle em BT, sem
  fd do hidraw ⇒ `disponivel()` é False e nada sobe. NUNCA publicamos uma
  source que só emitiria silêncio: um microfone falso é pior que microfone
  nenhum — é a mesma regra do medidor que prefere sumir a fingir zero.
* **Escrita de PCM NUNCA bloqueia.** O fifo do PipeWire é escrito em
  O_NONBLOCK e o quadro é DESCARTADO em EAGAIN. Bloquear ali penduraria a
  leitura do hidraw e estouraria a fila do kernel — em áudio ao vivo, atrasar
  é pior que perder.
~~~~

## external_mask

`src/hefesto_dualsense4unix/daemon/subsystems/external_mask.py (docstring do módulo)`. A máscara por aparelho: como cada controle aparece nos jogos.

~~~~text
Máscara por APARELHO — de CADA controle, externo ou DualSense (MÁSCARA-01/E1).

*"Como este controle deve aparecer nos jogos?"* — a escolha é de CADA controle,
e desde 08/09/2026 ela mora no **perfil**.

Este módulo é **o registro e a regra de herança**: onde a escolha mora enquanto
o daemon roda, como ela sobrevive ao reboot, o que ela NÃO promete, e — desde
15/08/2026 — qual máscara um jogador recebe quando não escolheu nenhuma. Ele não
adota externo, não cria gamepad virtual, não esconde ninguém do jogo e não
desenha tela — isso é a `E2`/`E3`/`E4` da MÁSCARA-01 e a `E3` da
LUGAR-À-MESA-01, que o usuário autorizou **depois** desta.

O DONO DA MÁSCARA É O PERFIL — DESDE 08/09/2026
------------------------------------------------

**NOTA DATADA — 08/09/2026 (MASCARA-NO-PERFIL-01).** A pergunta foi *"a máscara
por controle deve entrar no perfil, junto com luz, gatilho, vibração, som, mic e
sensores — ou fica da máquina?"*; a resposta de produto foi *"pode entrar sim"*. O
campo é ``profiles.schema.ControllerOverrides.mascara``, e quem o escreve aqui é
``profiles.manager.apply_controller_mascaras``, a cada ativação de perfil.

**FATO SUBSTITUÍDO.** O cabeçalho deste módulo dizia que *"a escolha é do
aparelho, não da configuração de jogo"* e que ela não podia morar no perfil
porque *"cada troca automática de perfil — cada alt-tab — faria o controle sumir
e voltar no meio da partida"*. A primeira metade caiu por decisão de produto; a
segunda **continua medida e não some**: trocar a máscara derruba e recria o
vpad. O que a torna suportável é que ninguém repinta quem não mudou —
``apply_controller_mascaras`` escreve peça a peça e :func:`vpad_ficou_para_tras`
compara antes de derrubar, então um perfil que repete a máscara de um jogador
não o faz sumir. A sprint que fechou a porta velha é
a sprint `MASCARA-01`
(seção *"Onde a máscara mora"*), e o que valia lá vale só até esta nota.

**O QUE ESTE REGISTRO É AGORA: um CACHE do perfil ativo, não o dono.** Ele
continua existindo por uma razão medida, e não por inércia — ``mascara_efetiva``
é consultada na criação de todo vpad **e no tique do co-op**, que compara para
decidir recriar; ler o perfil do disco ali seria a tempestade de syscalls que o
``gamepad._motores_do_perfil_ativo`` já pagou uma vez. Quem grava o gesto do usuário
(``gamepad.mask.set``) escreve nos DOIS: no perfil ativo, que é o dono, e aqui,
para valer agora.

A CONSEQUÊNCIA PARA QUEM LER ESTE ARQUIVO NO DISCO: uma entrada de
``controller_masks.json`` que o perfil ativo não repita **não sobrevive à
próxima ativação** — ela é apagada por :meth:`ExternalMaskRegistry.manter_somente`,
e aquele controle volta ao padrão. Não é escolha perdida, e não é dado a
defender. Apagar o arquivo com o daemon parado também não muda máscara nenhuma
de quem o perfil declara: a próxima ativação o reescreve.

**PERFIL CALADO DEVOLVE AO PADRÃO — DECISÃO, 09/09/2026.** A pergunta
aberta na entrega de 08/09 era *"um perfil que não fala de máscara devolve todo
mundo ao padrão, ou deixa cada um como está?"*; a resposta de produto foi *"Default é
Hefesto dualsense padrão"*. Nesta seção — e só nesta — ``None`` no perfil não é
*"sem opinião"*: é *"volte ao padrão"*. O padrão é o degrau de baixo desta
ordem, ou seja o ``mode.gamepad_flavor`` do perfil e, na falta dele, o
``DaemonConfig.gamepad_flavor``, que de fábrica é ``dualsense``.

DE QUEM É A MÁSCARA — DO JOGADOR, DESDE 15/08/2026
---------------------------------------------------

**NOTA DATADA — 15/08/2026 (MÁSCARA-POR-JOGADOR-01).** Até aqui este registro
não tinha chamador nenhum em ``src/``, e a razão estava escrita em
``profiles/schema.py``: *"``mode`` e a máscara do gamepad são da SESSÃO, não da
peça"* (decisão, 10/08/2026). **Ela reescreveu essa frase em 15/08/2026**:
vale só para o ``mode``. A máscara passa a ser **do jogador**, com a máscara do
jogo como **padrão herdado** — quem não escolheu nada segue o jogo, exatamente
como um campo em branco de ``ControllerOverrides`` herda a seção global.

A medição que separou os dois casos (documento
a sprint `MASCARA-POR-JOGADOR-01`): o ``mode`` é
estado do PROCESSO — existe um só e duas unidades pedindo modos diferentes não
têm resposta. A máscara **já tem um lugar por jogador**: o co-op cria um gamepad
virtual por controle e cada um carrega o próprio ``flavor``.

**A chave serve ao DualSense também, e sempre serviu.** O módulo nasceu para os
externos, mas :meth:`ExternalMaskRegistry._key` delega a
``ExternalIdentityRegistry._canonical``, que canoniza **qualquer** MAC de
hardware; e ``core.evdev_reader.discover_dualsense_evdevs`` — a função que o
co-op usa para achar cada jogador — já devolve exatamente esse MAC normalizado.
Nada precisou mudar no armazenamento: o que mudou foi **quem pergunta**.

QUEM PERGUNTA, E UMA VEZ SÓ
---------------------------

:func:`mascara_efetiva` é consultada uma vez na criação de todo gamepad
virtual, por ``virtual_pad.make_virtual_pad``, e no laço de recriação do co-op
(:func:`vpad_ficou_para_tras`). Os construtores (``UinputGamepad.for_flavor`` e
``UhidDualSense.for_flavor``) vestem a chave que recebem e não releem o registro
(A-MASCARA-DO-PAD-SE-DECIDE-SO-NA-FABRICA-01, 10/10/2026). A ``identity`` que ela
precisa chega do ``gamepad.py`` (o primário) e do ``coop.py`` (cada jogador), e a
escolha do usuário é gravada pela rota ``gamepad.mask.set``.

**Por que a fábrica resolve ANTES de escolher o backend:** o gate do
``_try_uhid`` usa a máscara que recebe. Se ele recebesse a do JOGO, um jogador
que escolheu ``dualsense`` numa sessão ``xbox`` teria o uhid vetado e cairia no
``uinput`` com máscara DualSense — que é o par degradado onde a vibração do jogo
morre (VPAD-05/SPRINT-GAME-RUMBLE-01).

RISCO NÃO MEDIDO — CONTROLES HETEROGÊNEOS NA MESMA SESSÃO
----------------------------------------------------------

**NINGUÉM MEDIU** se um jogo aceita dois vpads com máscaras diferentes ao mesmo
tempo (dois vistos como Xbox 360 e dois como DualSense). É plausível que o jogo
enxergue os quatro sem reclamar — são quatro devices distintos, como sempre
foram —, e é igualmente plausível que a camada de entrada dele (Steam Input, o
``gamecontrollerdb`` da SDL, ou um motor que escolhe UM esquema de prompts para
a partida inteira) troque prompts, embaralhe a ordem dos jogadores ou ignore o
que destoa. **Não prometa que funciona.**

O que mediria, e cabe numa sessão com a mesa cheia: quatro controles, um jogo
com Steam Input aberto, P1 em ``dualsense`` e P2 em ``xbox`` — e então olhar
três coisas, nesta ordem: (1) os quatro jogadores continuam existindo no jogo;
(2) os prompts de cada um saem na máscara dele, e não na do P1; (3) o rumble
chega nos quatro. Qualquer resposta "não" transforma a escolha por jogador num
recurso com aviso na tela, não num defeito a caçar no nosso lado.

O ARQUIVO É PRÓPRIO, E NÃO É UM BUMP DO ``controllers.json``
-----------------------------------------------------------

*(Continua valendo para ONDE o cache mora — o que mudou em 08/09/2026 é quem
manda nele, e está na nota acima.)*

A sprint de 25/07 pedia *"registro de identidade, no mesmo arquivo que já guarda
a ordem de preferência, com versão de esquema nova"*. Isso **caducou em
07/08/2026** — ver a nota datada na própria sprint. Quatro fatos MEDIDOS na
árvore fecham aquela porta, e os quatro estão registrados na
``REGRA-NAO-REGISTRO-01``:

1. ``identity.load`` (``identity.py:1639``) DESCARTA a fila inteira quando a
   versão do arquivo difere — um bump renumeraria a bancada;
2. ``identity._save_locked`` só aproveita as entradas do outro lado quando
   ``bruto.get("version") == CONTROLLERS_SCHEMA_VERSION`` (``:2170-2174``): o
   primeiro save de DualSense depois de um bump APAGARIA a fila dos externos;
3. ``payload: dict[str, Any] = {}`` é montado do zero (``identity.py:1537``) —
   chave nova de topo escrita pelo lado externo morre no primeiro save do outro;
4. ``merged_order_payload`` devolve exatamente ``{addr, kind, rank}``
   (``:555``) e ``order_entries`` descarta ``kind`` desconhecido (``:521``) —
   campo novo POR ENTRADA morre nos dois escritores.

Logo: **arquivo próprio** (:data:`_MASKS_FILE`) em ``config_dir()``, com
**versão própria** (:data:`MASKS_SCHEMA_VERSION`), chaveado pela identidade que
:func:`~...external_identity.identity_for_entry` já carimba. Sem bump, sem
migração, sem renumerar ninguém.

E a lição do item 3 é aplicada a ESTE arquivo, contra nós mesmos: o save é
read-modify-write e **preserva o que não entende** (chaves de topo e campos por
entrada que uma versão futura tenha escrito). Um arquivo cuja ``version`` não
seja a nossa não é lido **nem sobrescrito** — recusar a gravar é mais barato que
destruir a escolha de alguém.

O QUE ESTE REGISTRO NÃO PROMETE — os dois limites, GRAU MEDIDO
--------------------------------------------------------------

1. **Identidade volátil não atravessa a sessão.** ``dev:<instância HID>``,
   ``path:<node>`` e o endereço SINTETIZADO pelo ``usb_probe_degrade``
   (``02`` + VID + PID + bus) não identificam aparelho nenhum — ver
   ``external_identity._canonical`` (``:415-431``) e o MODO-01. Máscara
   pendurada ali vale na sessão e **não vai ao disco**: persistir seria gravar
   uma escolha em cima de uma chave que dois aparelhos diferentes podem
   dividir (CLONE-01).
2. **Máscara é por ROSTO, não por grupo.** A ``REGRA-NAO-REGISTRO-01``
   compartilha **rank**, nunca identidade: os dois endereços de hardware do
   8BitDo dividem um lugar na fila e continuam sendo duas chaves. Máscara posta
   num rosto **não vale no outro**. É o mesmo limite que aquela sprint declara
   para ``Profile.controllers`` (item 5 de *"O que esta sprint NÃO resolve"*), e
   a extensão natural — o lookup consultar os outros rostos do grupo — está
   deliberadamente fora deste desenho.

VALOR INVÁLIDO NUNCA VIRA XBOX
------------------------------

:func:`normalizar_mascara` é ESTRITA de propósito: devolve ``None`` para o que
não reconhece, em vez de cair no ``DEFAULT_FLAVOR``. O normalizador tolerante
(``uinput_gamepad.normalize_flavor``, que aceita sinônimos de CLI/IPC e cai em
``"xbox"``) é o certo para a linha de comando e o errado aqui: esta casa já
pagou o ``or "xbox"`` do editor de perfis, que transformava *"sem opinião"* em
*"exige Xbox"* e apagava giroscópio e touchpad no jogo do usuário sem que ninguém
pedisse (ESCOLHA-DELA-VENCE-01, E1). O catálogo de máscaras válidas é o
``FLAVORS`` do vpad — fonte única, para que uma máscara nova não precise ser
declarada em dois lugares.
~~~~

## bt_mic

`src/hefesto_dualsense4unix/daemon/subsystems/bt_mic.py (docstring do módulo)`. O canal de captura de cada DualSense por Bluetooth, como subsystem.

~~~~text
Subsystem: o canal de captura de CADA DualSense por Bluetooth (BT-MIC-01).

Embrulha `integrations/dualsense_bt_audio.py` no contrato `Subsystem` do
daemon (`start`/`stop`/`is_enabled`). É fino de propósito — toda a lógica de
protocolo, Opus e PipeWire mora no módulo de integração, que roda igual pelo
CLI (`mic bt`), pela GUI ou por aqui.

AS DUAS TRAVAS, LIDAS ANTES DE MEXER (CANAL-POR-CONTROLE-01, 03/09/2026)
------------------------------------------------------------------------
Decisão de produto, com as palavras do usuário e sem corrigi-las:
*"4 controles os 4 tem que ter canais de entrada unico pra cada qual."*  (noqa-acento)

Medido com os dois controles na mesa: existia **UM** canal, o do cabo.
O do rádio não publicava fonte nenhuma, e quem recusava eram duas travas
NOSSAS. A §2 da sprint manda achar o que cada uma protegia antes de tocá-las,
e a leitura é esta:

=====================  =========================  =============================
trava                  de onde veio               o que protegia
=====================  =========================  =============================
`habilitado_por_env`   `42213029`, 25/07/2026     privacidade + banda do rádio
`uniqs_declarados`     `598aa5a3`, 23/08/2026,    a mesma razão, mais o *"por
                       QUATRO-MICROFONES-01/E1    controle"* que o usuário pediu. Não
                       (decisão de produto: *"por       é precaução nossa: é o
                       controle"*)                INTERRUPTOR dela
=====================  =========================  =============================

**As duas são a MESMA razão em duas roupas**, e ela está escrita abaixo: a
ponte é um gesto explícito.

**A PERGUNTA QUE A §2 OBRIGA** — *"por que o cabo não precisa da mesma
proteção?"* — foi medida em 03/09/2026, com o controle do cabo na mesa::

    600  alsa_input...DualSense_Wireless_Controller-00.iec958-stereo  SUSPENDED

O canal do cabo **existe e está SUSPENDED**: publicado, e sem capturar nada
enquanto ninguém o abre. Ele não paga privacidade nem banda por existir.

**A ponte do rádio NÃO SABIA FAZER ISSO — e passou a saber em 06/09/2026**
(ONDA5-MIC-VIRTUAL-02). Aqui estava escrito, no presente, que
`PonteMicBluetooth.iniciar()` manda o `0x32` de LIGAR incondicionalmente e o
controle transmite áudio o tempo todo, ouvido ou não. Era verdade e deixou de
ser: o pedido agora SEGUE o estado da source — `RUNNING` (tem app gravando)
liga, qualquer outro desliga —, que é a mesma coisa que o cabo faz de graça.
Medido na bancada no mesmo dia: sem ouvinte `SUSPENDED`, com um `parec`
gravando `RUNNING`, e `IDLE` depois que ele sai (`integrations/
dualsense_bt_audio.ESTADO_COM_OUVINTE`).

**Logo a trava protegia a coisa certa pela alavanca errada** — ela negava o
CANAL para evitar a CAPTURA, e o cabo prova que os dois são separáveis. É
exatamente a distinção que a sprint faz: *"perder o padrão não é perder o
canal"*. **Hoje a distinção é do PRODUTO, e não só do argumento:** o canal do
rádio pode existir sem capturar, como o do cabo.

**Então a trava NÃO SAI: ela vira automática, e o critério explícito é o do
cabo — PROCURA.** A ponte sobe para o controle cujo canal alguém está tentando
usar, e o gesto que diz isso já existe e já é do usuário: o botão do microfone, que
desde 01/09 quer dizer *"eu falo por este controle"*
(`integrations/eleicao_de_microfone.py`). A exigência que MORRE é a de declarar
cada `uniq` à mão no `maquina.json` antes que ele possa ter canal.

**O que isso muda em quem chama:** `is_enabled` passa a ser sempre `True` — o
supervisor tem de estar de pé para atender o primeiro toque, e de pé ele não
captura nada: sem pedido e sem declaração, `alvos()` devolve `[]`, nenhuma
ponte sobe, nenhum `0x32` é escrito e a libopus nem é importada. O custo em
repouso é uma varredura de sysfs a cada `RECONCILIA_S`.

**ELE SOBE SOZINHO DESDE 17/09/2026, E A RAZÃO DE NÃO SUBIR CADUCOU.** Aqui
estava escrito, no presente, *"por que ele não sobe SOZINHO, e a razão continua
de pé"* — privacidade e banda, as duas abaixo. **Ela revogou as duas em
25/08/2026, por escrito**, em `docs/data/decisoes-de-produto.csv`: a id 37
(D-AUDIO-E-GIRO-NASCEM-LIGADOS) e a id 38 (D-O-MIC-LIGADO-VALE-NO-RADIO), esta
com as palavras do usuário — *"LIGADO SEMPRE, NOS DOIS TRANSPORTES, COM A TELA DIZENDO
O PREÇO… o que caduca é o padrão desligado"*. A decisão nunca foi implementada,
e em 17/09/2026 o usuário pediu a mesma coisa pela TERCEIRA vez:

    *"segue por default mudo. eu preciso lembrar de clicar no icon do mic pra
    ativar e ele ser reconhecido. isso deveria ta  # (noqa-acento: citação literal)
    ativado por padrao"*  # (noqa-acento: citação literal), 17/09/2026

**O QUE MUDOU, E O QUE NÃO MUDOU.** Quem diz a palavra na CHEGADA do controle é
`daemon/subsystems/hotkey.nascer_no_ar`, chamado pelo gancho de conexão
(`daemon/connection.nascer_o_microfone_ao_conectar`) — NASCE-LIGADO-MIC-01.
Nada aqui virou persistência: as portas de saída do latch continuam todas de
pé, quem sai da mesa perde o pedido e a palavra, e nada volta do disco. O que
mudou é que a chegada volta a dizer a palavra — e é por isso que ela não
clicava uma vez, clicava *toda vez*.

**E O SILÊNCIO DO USUÁRIO CONTINUA VENCENDO.** O nascimento recua diante das duas
formas de ela ter pedido para calar: o mudo daquele controle no `maquina.json`
(a `ProfileManager.o_controle_pede_silencio`, O-MUDO-E-DO-CONTROLE-01) e o bit
do mudo já aceso no aparelho.
Sem isso a SOM-MIC-REPLUG-01 — *"o silêncio que o produto promete e não
entrega"* — voltaria pela porta da frente.

**AS DUAS RAZÕES QUE ELA REVOGOU FICAM ESCRITAS**, porque a segunda continua
sendo a CONTA que diz quantos microfones cabem numa mesa, e porque apagá-las
deixaria a próxima pessoa sem saber que o padrão desligado já foi política:

1. **Privacidade.** Era: *"um microfone que liga sozinho quando o daemon sobe é
   inaceitável, por melhor que seja a intenção"*. Revogada por ela — e o que
   sobrou da preocupação é o recuo diante do silêncio pedido, acima.
2. **Banda do rádio.** Medido ao vivo (2026-07-25, DualSense por BT nesta
   máquina): com o mic desligado o controle entrega ~260 reports de input/s;
   com o mic ligado a MESMA banda passa a carregar ~106 quadros de áudio/s e
   os reports de input caem para ~170/s. O total de pacotes fica igual — o
   áudio não é de graça, ele divide o link. É por isso que a conta é POR
   ADAPTADOR, e é ela que diz quantos microfones cabem numa mesa.

   NOTA DATADA — 22/08/2026, decisão de produto. Aqui estava escrito que *"quem usa
   gyro aiming perde resolução de integração (o espelho de motion mira
   250 Hz)"*. **Aquilo comparava réguas de transportes diferentes** e a
   remedição de 11/08/2026 o derrubou: 250 Hz é a taxa NATIVA DO CABO, e no
   rádio o físico nunca teve taxa — entrega em RAJADA, medida "entre ~55 e
   ~392 Hz" com o mic DESLIGADO, p95 de intervalo em 187 ms
   (`core/physical_report_reader.py`, "A taxa do rádio é RAJADA"). Um número
   que oscila 55 a 392 não perde resolução por passar a valer 170 de média: a
   premissa da frase não existia. Ela é a armadilha nº 1 desta casa — medir
   contra a régua errada produz alarme convincente e falso.

   O que fica: o microfone **não é trade-off contra giroscópio**. O alvo dela,
   textual em 22/08, é *"a mesma experiência do controle da Sony como se
   tivesse jogando no PS5"* — lá tudo funciona junto, e a conta de três
   adaptadores diz que aqui também cabe. O que continua verdadeiro é a conta
   do link, e ela é o que o orçamento da mesa mede.

POR CONTROLE, E POR QUE UM `bool` NÃO SERVE (QUATRO-MICROFONES-01, 22/08/2026)
------------------------------------------------------------------------------

Até 22/08 o gate era `DaemonConfig.bt_mic_enabled: bool` — **um** campo, lido
por três lugares e escrito por nenhum. A decisão de produto é literal: *"por
controle"*, um interruptor por card, quatro independentes ao mesmo tempo.

**Um `bool` não sustenta quatro independentes** — ele só sabe dizer "todos" ou
"nenhum", e a bancada tem quatro DualSense em três adaptadores. Somar um `bool`
por controle no `DaemonConfig` também não serve: o `DaemonConfig` é config de
PROCESSO, e o número de controles muda por hotplug, no meio da sessão.

O que substituiu: **um CONJUNTO de `uniq` ligados**, e a ausência é o desligado.
Três razões, e a terceira é a que fecha a escolha:

* a chave é o `uniq` — endereço de hardware, doze hex — porque ele é o que
  sobrevive a hotplug, a renumeração de jogador e à troca do nó `hidrawN`. O
  número de jogador não sobrevive a nenhum dos três;
* **eram DOIS conjuntos desde 18/09/2026**, e o segundo é o que a inversão
  pediu: `bt_mic_uniqs` (quem ela ligou) e `bt_mic_recusados` (quem ela
  desligou). Até aqui havia um só, e o comentário nesta linha dizia que um
  `false` gravado *"é um valor de catálogo para o silêncio, e é por essa porta
  que o default entra disfarçado de escolha do usuário"*. Isso valia com o default
  sendo o silêncio; com a ordem de produto — *"todos os controles tem que nascer com
  tudo mic, giroscopio e afins"* — o `false` virou a ÚNICA forma de ela dizer
  não, e não gravá-lo é que deixaria o produto decidir por cima dela;
* a fonte é **chamável**, nunca uma cópia: o `machine.declare` relê o
  `maquina.json` e REBINDA `daemon._maquina` no "Aplicar" (`ipc_handlers.py`),
  então uma cópia tirada no boot ficaria velha no instante exato em que ela
  acabou de escolher. É o mesmo desenho do `DaemonConfig.orcamento_da_mesa`.

QUEM GANHA PONTE, em três caminhos e nesta ordem (03/09/2026)
--------------------------------------------------------------
1. **PROCURA** — `PEDIDOS`, o registro deste módulo. É o caminho automático que
   substituiu a exigência de declarar à mão, e quem escreve nele é a eleição do
   microfone quando o canal daquele controle não está no ar. Um pedido vale
   enquanto o controle estiver na mesa: ao cair do rádio ele é esquecido, e uma
   reconexão não ressuscita microfone nenhum;
2. **declaração** — `DaemonConfig.bt_mic_uniqs` (fiada por `run()` a partir do
   `maquina.json`). Continua valendo inteira: quem já marcou um controle
   continua com a ponte de pé sem precisar tocar em botão nenhum;
3. **a env** `HEFESTO_DUALSENSE4UNIX_BT_MIC=1` — o caminho à mão, que vale para
   TODOS os controles. É o que ela sempre significou, e quem a exporta está
   pedindo a mesa inteira de propósito.

**E DESLIGAR CONTINUA DESLIGANDO.** Tirar a marca do card no "Aplicar" derruba
a ponte mesmo que houvesse um pedido aberto: o laço vê o `uniq` SAIR da
declaração e solta o pedido junto (`_soltar_os_que_ela_desmarcou`). Sem isso o
gesto mais explícito que ela tem — o interruptor — perderia para um toque de
botão feito minutos antes, que é o oposto de quem manda.

O laço de reconciliação vive num `threading.Thread` e DORME num `Event` entre
as varreduras — nunca um laço apertado, nunca um `sleep` de polling de dados.
O áudio em si não passa por aqui: cada ponte tem a própria thread bloqueada no
`read()` do hidraw (o áudio é o relógio).
~~~~

## ControllerOverrides

`src/hefesto_dualsense4unix/profiles/schema.py (classe ControllerOverrides)`. Os overrides por controle dentro do perfil e a fila do que falta.

~~~~text
Overrides POR CONTROLE dentro do perfil (PERFIL-02, 2026-07-16).

Campo ``None`` = sem opinião: o controle herda a seção GLOBAL do perfil
(merge POR CAMPO na aplicação, PERFIL-01 — override parcial nunca apaga a
cor global no replug).

**A EXCEÇÃO É UMA, E É DECISÃO (09/09/2026):** em ``mascara``, ``None``
quer dizer *"volte ao padrão"* — *"Default é Hefesto dualsense padrão"*. O
controle que o perfil não declara **perde** a máscara própria que estivesse
valendo, em vez de mantê-la. A diferença existe porque a máscara é a única
seção cujo estado anterior sobreviveria FORA do perfil: as outras seis são
reaplicadas por inteiro a cada ativação, e a máscara morava num registro
próprio que atravessava a troca. Ver o campo, lá embaixo, e
``manager.apply_controller_mascaras``, que mede o que a devolução custa.

O ALVO É TUDO — DECISÃO, 02/09/2026
-----------------------------------------
*"acelerômetro, giroscópio, e todas as demais features. **é tudo mesmo**"*
— e ela marcou junto: teclas e ações de botão, mouse e teclado emulado,
modo (Hefesto/Xbox/Steam) e microfone.

**O QUE ISSO DERRUBA:** esta docstring trazia uma lista de seções *"FORA
porque NÃO TÊM RESPOSTA HONESTA por unidade"*. Essa lista caiu — a resposta
de produto é que tem resposta, e é por controle. As medições que sustentavam a
lista continuam de pé, mas mudaram de papel: não são recusa, são FILA DE
ENGENHARIA, e estão abaixo com o que falta construir em cada uma.

**A ORDEM, e ela não se inverte:** primeiro o caminho por unidade EXISTIR,
depois o campo entrar aqui. Campo que grava e ninguém lê é pior que campo
nenhum — ele faz a tela prometer: a coluna da aba Perfis acende dizendo
*"este controle tem ajuste próprio"* sobre um valor que nada aplica. Há
régua, e ela é exaustiva nos dois sentidos:
``tests/unit/test_perfil_por_controle_o_campo_espera_o_caminho.py``
classifica CADA campo desta classe contra o consumidor por-``uniq`` que o
lê, e reprova tanto campo sem consumidor quanto consumidor órfão.

O QUE JÁ CHEGA À PEÇA — e é só o que está declarado abaixo
----------------------------------------------------------
- ``leds`` (lightbar + player_leds + brilho) e ``triggers``, desde
  PERFIL-02: ``manager._controllers_to_specs`` os converte em ``OutputSpec``
  por MAC, e o brilho sozinho vira fator em ``_controllers_to_led_scales``;
- ``rumble``, desde POR-UNIDADE-01 (10/08/2026):
  ``manager._controllers_to_rumble_scales`` devolve ``{uniq: fator}``, que
  o backend aplica na saída de cada handle (``set_rumble_scales``);
- ``speaker``, da mesma sprint: ``manager.apply_controller_speakers`` chama
  ``apply_speaker(uniq=...)`` → ``apply_profile_speaker(uniq=...)`` →
  ``set_speaker_volume(uniq=...)``, com o alvo no parâmetro em toda a
  escada;
- ``mic``, desde MIC-QUINTO-AJUSTE-01 (03/09/2026, decisão de produto):
  ``manager.apply_controller_mics`` chama ``apply_mic(uniq=...)`` →
  ``apply_profile_mic(uniq=...)`` → ``set_microphone_mute(uniq=...)``. É um
  subconjunto — só o ``muted`` —, e ``ControllerMicOverride`` diz por
  medição o que ficou de fora e o que cada um espera;
- ``mascara``, desde MASCARA-NO-PERFIL-01 (08/09/2026, decisão de produto):
  ``manager.apply_controller_mascaras`` escreve a máscara
  daquela peça no registro que ``external_mask.mascara_efetiva`` consulta na
  criação de cada gamepad virtual, e é o perfil que passa a mandar (ver o
  item 3 da fila abaixo, que dizia o contrário até 08/09).
- ``movimento``, desde A-MIRA-POR-MOVIMENTO-NA-TELA-01 (24/09/2026, a
  palavra de produto: o chip «Mira Virtual» no cartão de cada controle):
  ``manager._controllers_to_miras`` monta o arranjo daquela peça por cima
  do do perfil, e o tique o pergunta com o ``uniq`` de cada jogador
  (``roteador_de_movimento.da_peca``).

Fora por decisão, e não por falta de caminho:
- ``label`` — identidade visível é outra frente (4P-03);
- ``mic_led`` — o mic jamais é colateral de troca de perfil
  (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01).

A FILA DO QUE FALTA, ORDENADA POR CUSTO — medida em 02/09/2026
---------------------------------------------------------------
1. O que sobrou do ``mic``, e são os DOIS campos que
   ``ControllerMicOverride`` recusa na borda com a razão escrita. O
   ``muted`` entrou em 03/09/2026 (MIC-QUINTO-AJUSTE-01); faltam:

   - ``volume`` — **A COSTURA DO APPLIER FOI FEITA EM 03/09/2026**, e o que
     falta agora é OUTRA metade. Esta linha dizia que
     ``lifecycle.apply_profile_mic`` "hoje usa a rota GLOBAL
     ``fonte_de_captura_do_controle()``"; **FATO SUBSTITUÍDO**: ele passou
     a chamar ``fonte_de_captura_do_uniq(uniq)`` quando recebe ``uniq``, e
     **não cai** para a rota global quando o ``uniq`` não resolve — cair
     seria escrever no microfone do vizinho, que é o estrago inteiro.
     ``tests/unit/test_o_volume_do_mic_segue_o_controle.py`` morde as duas
     formas.

     O QUE FALTA É ABRIR O CAMPO AQUI, e é decisão à parte: abrir muda o
     que o perfil do usuário aceita no disco. Há teste que reprova no dia em que
     alguém o abrir, para que esse dia seja DELIBERADO;
   - ``button_toggles_system`` — ``hotkey.mic_button_loop`` precisa
     consultar o override daquele ``uniq`` antes de
     ``daemon.config.mic_button_toggles_system``, que é um por máquina.

   **NOTA DATADA — 02/09/2026.** Esta docstring dizia que o ``mic`` não
   cabia aqui porque *"o ``EventTopic.BUTTON_DOWN`` publica ``{"button",
   "pressed"}`` e não carrega uniq, então o laço do mic não tem como saber
   de qual peça veio o toque"*. A frase sobre o ``BUTTON_DOWN`` continua
   verdadeira e o motivo dela morreu: o gesto do microfone deixou de passar
   por ali. **O item mais caro da lista virou o mais barato.**

2. ``giroscopio`` e ``acelerometro`` — **SAÍRAM DA FILA EM 04/09/2026**
   (SENSOR-DE-VERDADE-01). O campo é ``sensores``, e ele entrou porque o
   caminho por unidade nasceu primeiro: ``sensor.set`` no IPC, o registro
   por ``uniq`` (``core/virtual_motion.REGISTRO``), a meia-janela zerada no
   que o vpad entrega ao jogo e o ``EVIOCGRAB`` no nó "Motion Sensors"
   pelo ``SensorHub``. Quem o lê por peça é
   ``manager.apply_controller_sensores``.

   **FATO SUBSTITUÍDO:** esta entrada dizia *"não existe no produto nada
   que desligue um sensor"* e que o hub *"só LÊ"*. Passou a existir, e o
   hub ganhou o braço do grab. O que a medição de 04/09 acrescentou, e
   nenhuma versão desta fila previa, é que **o nó evdev não é por onde o
   SDL lê o giro** — ele lê pelo ``hidraw`` — e que em Modo Nativo o
   daemon não está nesse caminho. O limite está escrito em
   ``ControllerSensoresOverride`` e sai na resposta do método.

3. ``mode``, e ele é o único da fila com DOIS eixos. O ``mode`` é da SESSÃO
   (decisão, 10/08/2026): existe um só, e o daemon não pode estar em
   dois ao mesmo tempo. **A MÁSCARA do gamepad NÃO está nessa frase** —
   ela ficou larga demais e ela a reescreveu em 15/08/2026
   (MÁSCARA-POR-JOGADOR-01): o co-op cria um gamepad virtual por controle e
   cada um carrega o próprio ``flavor``, então a máscara **é do jogador**,
   com a do jogo como padrão herdado.

   **A MÁSCARA SAIU DESTA FILA EM 08/09/2026 — decisão de produto, MASCARA-NO-
   PERFIL-01.** A pergunta foi *"a máscara por controle deve entrar no
   perfil, junto com luz, gatilho, vibração, som, mic e sensores — ou fica
   da máquina?"*, e a resposta foi *"pode entrar sim"*. **FATO
   SUBSTITUÍDO:** esta entrada dizia *"a máscara não é campo daqui"* e que
   trazê-la *"exige antes uma troca de máscara que NÃO derrube o vpad"*. O
   campo é o ``mascara`` declarado abaixo, e a razão de a porta ter sido
   aberta sem essa troca é a consequência que ela sentiu: **trocar de perfil
   trocava o modo e não trocava a máscara de ninguém** — um perfil de jogo
   que precisa do P2 em Xbox não tinha como dizer isso.

   O custo medido continua de pé e não some por decisão: trocar a máscara
   **derruba e recria o gamepad virtual**. O que o desenho garante é que
   isso só aconteça para quem MUDOU — ``apply_controller_mascaras`` escreve
   peça por peça e ``external_mask.vpad_ficou_para_tras`` compara antes de
   recriar, então um perfil que repete a máscara de alguém não o faz sumir
   no meio da partida (é a regra da NUMA-03). Isso vale inclusive para o
   perfil CALADO, que desde 09/09/2026 devolve todo mundo ao padrão
   (decisão de produto): a devolução apaga a entrada, mas só cai o vpad de quem
   estava FORA do padrão — medido, 0 de 4 com a mesa já no padrão.

   ONDE A MÁSCARA É RESOLVIDA, e a resposta continua num arquivo só:
   ``daemon/subsystems/external_mask.py``. O que mudou é o papel dele — de
   DONO da escolha para CACHE do perfil ativo, consultado por
   ``mascara_efetiva`` na criação de todo vpad e no tique do co-op. Ler o
   perfil do disco naquele tique seria a tempestade de syscalls que o mapa
   de motores do ``gamepad.py`` já pagou uma vez.

   O ``mode`` fica na fila; ele é o eixo que continua sendo da sessão.

4. ``mouse``, ``key_bindings``, ``button_actions``, ``teclado_emulado`` e
   ``suppress_desktop_emulation``. Os cinco esbarram na MESMA medição, e
   ela continua de pé: ``PyDualSenseController.read_state`` diz, em
   comentário de código, que *"INPUT vem SEMPRE do controle PRIMÁRIO"* e
   que a emulação de mouse/teclado/gamepad é **single-controller por
   construção**; o ``Daemon`` tem UM ``_mouse_device`` e UM
   ``_keyboard_device`` (``daemon/lifecycle.py``), alimentados por um
   ``read_state()`` por tique. Guardar por controle é fácil; **fazer valer**
   exige um caminho de ENTRADA por unidade — ler cada peça e despachar para
   o device dela. É o item mais caro da fila, e é o que destrava os cinco de
   uma vez.

5. ``touchpad``. Continua sem campo em lugar nenhum do perfil e sem tela
   aprovada que ofereça interruptor: na aba Controles ele é leitura viva.
   **É pergunta aberta para ela, não dívida com dono** — inventá-lo aqui
   seria feature nova.

A CONTRADIÇÃO ABERTA, E É DO USUÁRIO — não se fecha escrevendo código
-------------------------------------------------------------------
Três frases desta casa não cabem juntas, e a decisão de 02/09 as põe frente
a frente:

- o contrato do topo desta classe: **campo ``None`` = sem opinião**, e
  perfil que não pediu nada não impõe nada;
- ela, em 18/08/2026, derrubando o princípio geral: *"o perfil tem de
  guardar tudo"*;
- ``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` (25/08): áudio e giroscópio nascem
  **LIGADOS** em todo jogo — que é um default, não uma ausência.

Com "é tudo por controle", os três precisam ser reconciliados POR ELA. Está
registrado, não resolvido.
~~~~

## o boot e o último jogo (`daemon/connection.py`, `utils/session.py`)

`D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO` (14/10/2026): o perfil do jogo fica depois
que ele fecha, até ela mudar ou outro jogo iniciar, e o reinício do serviço não é
nenhum dos dois. Medido no mesmo dia: o daemon reiniciou e subiu na escolha à mão
(«Lure Of Passion»), com o gamepad desligado, por cima do perfil do último jogo,
porque a memória dele era só do processo (`AutoSwitcher._perfil_do_ultimo_jogo`).

A cura: o autoswitch e o lançamento (`origin="launch"`) gravam o perfil em
`ultimo_jogo.json` só na troca; o `_o_nome_que_o_boot_restaura` o põe depois do
Freestyle e do jogo em cena e antes da escolha, e o primeiro pad nasce no modo
dele (`perfil_que_o_boot_restaura`). O gesto dela (`gravar_a_escolha`) e o perfil
apagado (`ProfileManager.delete`) tiram a memória. O `resolve_boot_profile`
continua sendo a escolha do usuário: a aba Perfis destaca o que ela ativou, não o
do jogo.

**A corrida do boot** (medida às 20h52 de 14/10/2026, com o `dev` `7b5901cca`): o
Sackboy fechou, a Steam saiu e o serviço reiniciou com o terminal em foco. O
primeiro tique do autoswitch chegou 1,8 s ANTES do restauro, com a crença `None`,
e a queda do «sem candidato» foi à escolha à mão («Lure Of Passion»); o restauro
pôs o Sackboy, e o tique seguinte pôs o «Lure» de novo. O `_activate` ainda gravou
o «Lure» no `ultimo_jogo.json`, porque ele tem regra `steam_app_3851570` e passava
por perfil de jogo: o disco perdeu o jogo de verdade. A cura não depende de ordem
nem de tempo: a queda do «sem candidato» tem um dono, o
`AutoSwitcher._o_ultimo_jogo_que_vale`, que devolve o último jogo antes da escolha
também com a crença vazia. A memória do autoswitch é o espelho do disco, relida no
primeiro tique e sempre que outro troca o perfil (`_perfil_corrente`: o boot, o
lançamento, o gesto do usuário); o disco só vale quando a crença está vazia ou
aponta o próprio jogo, para que o perfil que outro pôs por cima não volte ao jogo.
E o perfil que entra pela escolha nunca grava nem apaga a memória do jogo.

Nota datada de 01/10/2026, que morava na docstring do `_o_nome_que_o_boot_restaura`:
ali morava a RESTORE-ESCOPO-01 (22/07), que pulava todo perfil com regra de janela,
e o Freestyle entrava no lugar (O-MODO-FREESTYLE-03). No disco do usuário isso é
todo perfil que não é o Freestyle: medido no diário de 28 e 29/09, seis boots com a
sessão em Pro Jank Footy, e nenhum abriu no perfil que ela tinha ativado. A decisão
de 29/09 revogou a regra para a escolha do usuário.


## o gadget estacionado (`integrations/uhid_gamepad.py`)

O jogo grava o device KS no lançamento com o GUID daquela hora, e o GUID sai do
`usb_device` (`DEVNUM`, `USEC_INITIALIZED`): remontar o gadget muda o GUID, e o
som da partida se perde (a cura 7 do `docs/process/estudos/2026-10-06-o-engasgo-tem-dono/REPASSE.md`).
Por isso, com jogo aberto, o gadget do aparelho que saiu fica de pé, parado no
neutro, e o aparelho que volta o retoma.

**O fantasma se decide pela adoção** (O-P3-VOLTA-INTEIRO, medido às 21h57 de
14/10/2026): o kernel levou 14 s para devolver o `hidraw` do P3, e o prazo de
10 s contado do estacionamento derrubou o gadget um segundo antes de o co-op o
retomar. O dono da decisão é a fábrica do pad (`virtual_pad.make_virtual_pad`,
por onde passa o pad do P1 e o do co-op, no cabo e no rádio): o pad que retomou
o gadget já o tirou da vaga, e o que nasce sem retomá-lo (outra máscara, o
uinput) o derruba na hora. Só o aparelho que está aqui e que nenhuma adoção
decide (a emulação desligada) desce pelo prazo, contado de quando o vigia o viu
de volta. O endpoint de háptica do aparelho segue o gadget: com jogo aberto, ele
fica enquanto a interface em que se ancora ainda é a do gadget dele
(`AltoFalanteSubsystem._aparelhos_de_pe` pergunta `a_porta_e_dele`). Vale para o
estacionado, para o pad do P1 que espera o posto sem descer e para o co-op que
segura o pad na troca de transporte. O jogo ocioso não toca no nó, mas o guardou
pelo contêiner do gadget. Sem jogo, o endpoint desce como antes. Só o laço do cabo
e a ponte do rádio se soltam, porque o aparelho saiu da mesa. O nó de som e o
microfone descem como antes: eles não declaram `sysfs.path`, e o jogo não os
acha pelo contêiner.

## o Aplicar e a trava da mão (`profiles/manager.py`, `ProfileManager.reaplicar`)

O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 (01/10/2026): o «Aplicar» mandava o
`profile.apply_draft`, que levava menos da metade do perfil (ficavam de fora o
volume e o ganho do microfone, os sensores, a máscara, a mira, o modo e a política
de vibração). Desde então ele roda a mesma cadeia da ativação (`_ativar`), e os
appliers recebem a origem `manual` (`D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR`).

`D-1410-O-APLICAR-SEGURA` (14/10/2026): a D-0110 deixava o «Aplicar» sem a trava
da troca à mão, e com o terminal em foco o autoswitch caía no «sem candidato» e
devolvia a escolha aos 12 s (`DEFAULT_DEBOUNCE_SAIDA_SEC`), por cima do perfil que
ela tinha aplicado. Agora o `reaplicar` arma a trava com o mesmo dono do «Ativar»
(`armar_a_trava_da_mao`), e quem a solta é o mesmo de sempre: o próximo gesto
dela, outro jogo com perfil em foco, o lançamento de um jogo com perfil
(`_a_trava_da_mao_segura`, `origin="launch"`). Ele continua sem gravar a escolha
nem o último jogo, que é a parte da D-0110 que fica: o boot não aprende um perfil
que ela não escolheu. **Só o gesto prende** (parte 3, as respostas dela, 14/10/2026: *«Só o Aplicar prende»*). O funil dos
ajustes das abas (`interface/pacotes/perfil.gravar_e_reaplicar`) também passa pelo
`profile.reaplicar`, mas sem o parâmetro `prender`: o ajuste numa aba não arma a trava, e o
autoswitch segue trocando de perfil por janela depois dele (Kodi, Navegação). Quem pede `prender`
é só o «Aplicar» do rodapé e o «Voltar à de ontem» (`ponte.profile_reaplicar(nome, prender=True)`);
o padrão do IPC é sem trava, e `tests/unit/test_o_aplicar_segura.py` nomeia os chamadores.

## O sensor.set (`daemon/ipc_handlers.py`, `_handle_sensor_set`)

Decisão de 04/09/2026: *«ele tem que funcionar de verdade. ambos independente do modo e da mascara.»* <!-- noqa-acento: citação literal -->

TRÊS ESCRITAS, a ordem é o contrato:

1. o registro vivo (`core/virtual_motion.REGISTRO`), que o report consulta a ~250 Hz e o jogo sente;
2. o perfil (`ControllerOverrides.sensores`), para sobreviver ao replug e à troca de perfil;
3. o `EVIOCGRAB` no nó «Motion Sensors» (e, desde 15/10/2026, no «Touchpad»), pelo `SensorHub`, que alcança
   quem lê evdev direto.

A resposta diz qual metade pegou (SENSORES-NO-JOGO-02, 13/09/2026, §1): o zero em Modo Virtual era da libSDL2
2.30.0 do sistema (nos runtimes da Steam o vpad expõe os dois sensores, pareados pelo `uniq`); em Nativo o giro
chega ao SDL pelo `hidraw` do físico, onde o daemon não está no caminho. Logo o alcance é parcial e a resposta o
diz, em vez de um «aplicado» falso.

O `touchpad` (O-TOQUE-LIGADO-OU-DESLIGADO-POR-CONTROLE-01) faz as mesmas três escritas. Desligado com jogo aberto
zera os contatos no `REGISTRO.filtrar` e o hub agarra o nó; Ligado só agarra quando o jogo recebe o toque pelo
vpad (hoje: a máscara efetiva da peça é DualSense). `touchpad_alcance` é `hidraw` no Nativo e com o Steam Input
do jogo ligado, onde só o nó do sistema (o cursor) é alcançado.

## o Testar da aba Vibração (`interface/pacotes/a05_vibracao.py`, `testar`)

Pedido de 07/09/2026: *«o botão Testar tem que ficar em estado de ligado e ir refletindo os slicers ao vivo
comigo. E se eu clicar em Parar ele para de testar»*. Era um pulso de meio segundo, e o pulso não responde
*«quanto é 40%?»*: a mão precisa estar no controle enquanto a outra arrasta a barra. O `_refrescar_o_teste`
reenvia o par a cada mudança de barra, e a mão só volta ao jogo quando ela clica em Parar.

Um teste por controle (03/10/2026, ela: *«vibração e háptico é por cada controle e precisam funcionar em
independente. hoje se eu clico em um o outro controle para de ter o efeito»*): o pedido leva o `uniq`
(`rumble_set_checked(..., uniq=...)`), o serviço guarda um par por controle e a aba não mira mais o seletor
global (`controller.target.set`), que fazia o serviço inteiro seguir o último clique. O Testar de um controle só
cala o teste da háptica DELE (os dois se excluem no mesmo controle, D-0210).

A checada, e não a crua: a recusa do modo nativo vem no corpo da resposta, e foi por não a ler que a aba
anunciou «vibração travada» com o motor parado (NATIVO-RUMBLE-01). O par sai reduzido pela barra de cada motor
(`_par_das_barras`, para a inversão `weak`/`strong`).

Com `padrao` (15/10/2026, A-ABA-VIBRACAO-DO-TODO-01): Batida, Onda e Tranco tocam uma vez pela fila do controle
(`padroes_de_vibracao.tocar`), e a mão volta ao jogo sozinha no fim.

## luz_animada (`daemon/subsystems/luz_animada.py`)

O efeito vive no perfil como texto (`base;cores;ritmo`), e não como nome da biblioteca da interface: o perfil
exportado anima igual em outro computador, e o daemon não lê a `luz_meus_efeitos` da interface. Texto ilegível
volta `None` (luz fixa), porque um enfeite não derruba o perfil.

O quadro pinta a barra sem entrar em camada nenhuma (`pintar_a_barra_sem_lembrar`), e ao sair do efeito o laço
devolve a barra ao desejado (`reassert_resolved_outputs`). A camada do jogo só escreve com o jogo em foco
(`set_game_output_for` retém a luz enquanto a autoridade é `daemon`). A da usuária foi a primeira escolha e caiu
na conferência de 15/10/2026, com o backend real: o quadro tomava o lugar da cor do perfil daquele controle (o
controle voltava na cor global do perfil depois da «Luz fixa»), soltava a cor que o jogo pintou, e o soltar
apagava o preto do «Sem efeito» meio segundo depois do clique, reacendendo a barra.

O pulso do tiro (`AtuadorDaLuz`) pinta pela camada do jogo e segura a barra até a volta; enquanto
`TatoVivo.segurando(CANAL_LUZ)` tem o controle, o efeito espera sem escrever, e o primeiro quadro da volta sai
mesmo igual ao último. Sem isso o quadro seguinte, 33 ms depois, apagava o pulso.

A política de «quem manda» é a `tato_vivo.decidir`, perguntada como se houvesse jogo: no Modo Nativo e com o jogo
pintando a barra o laço cala. Sem pad virtual não há efeito. O piscar tem o teto de 3 Hz da WCAG 2.3.1, o mesmo do
pulso por tiro; o respirar e o arco-íris saem a 30 quadros por segundo no máximo, e quadro igual não sai.

## o `resolver` das ações de botão (`core/acoes_de_botao.py`)

A docstring antiga, movida para cá em 15/10/2026 (a do código ficou com o contrato):

    As escolhas do perfil, separadas por QUEM as atende.

        Devolve três sacolas, e a terceira é a que impede o silêncio:

            do_mouse    botão -> `BTN_*`, para o `UinputMouseDevice`
            do_teclado  botão -> tupla de `KEY_*`/`__OSK__`, para o teclado virtual
            sem_dono    os botões cuja escolha ninguém atende HOJE

        O PS NÃO ESTÁ EM NENHUMA DAS TRÊS, e tem porta própria: :func:`acao_do_ps`.
        O atendente dele não é device — é o callback do `ps_solo`. E os botões
        CALADOS também não estão em nenhuma: quem os nomeia é :func:`botoes_calados`,
        porque o device de mouse precisa saber quais foram calados de propósito para
        tirá-los dos mapas do d-pad e do tap.

        `escolhas=None` devolve o de fábrica — é o mesmo contrato de
        `Profile.key_bindings`, e vale a mesma frase do esquema: `None` HERDA, `{}`
        seria "nada em botão nenhum", que é outra coisa.

        `key_bindings` É A CAMADA DO MEIO — 06/09/2026, ONDA3-MOTOR-01. Ela existe
        porque o `apply_button_actions` reescreve o conjunto INTEIRO do teclado
        virtual com o que sai daqui, DEPOIS de o `apply_keyboard` ter escrito o que
        o usuário digitou na janela antiga: sem herdar, todo atalho dela morria na
        ativação seguinte de qualquer perfil que tivesse `button_actions`. As regras
        e a razão de o `r3` ficar fora estão em :func:`tabela_efetiva` e em
        :data:`DOMINIO_DO_TECLADO`. Omitir o parâmetro é o contrato de antes, byte
        a byte — os três chamadores que não o passam não mudam de resposta.

        AS DUAS LINHAS DOS ANALÓGICOS são lidas pelo device: o token PRÓPRIO
        (`__CURSOR__` na esquerda, `__ROLAGEM__` na direita) é o de fábrica e não
        viaja; `— Nada —` desliga o eixo e chega por :func:`botoes_calados`; qualquer
        outro token desliga e viaja em `do_mouse`, e a linha cai em `sem_dono`, porque
        ninguém atende aquela escolha. A exceção são as teclas do analógico
        (:data:`TECLAS_DO_ANALOGICO`): o `TabelaNoJogo` as emite, e a linha tem dono; em
        botão que não é analógico elas não têm dono. Antes disto o cursor andava qualquer que fosse
        a escolha, e a tela oferecia a linha sem dono.

        OS DOIS GATILHOS SÃO LINHA PRÓPRIA, sem espelho no `cross` e no `triangle`:
        `l2` e `r2` entram em `do_mouse` ou em `do_teclado` como qualquer botão.

## As barras e as listas por peça (`app/ipc_bridge.py`, `rumble_motores_set`)

Decisão, 04/09/2026: a barra não manda o par `rumble.set` agora, ela é POLÍTICA e MULTIPLICA o
degrau da coluna (`efetivo(motor) = degrau x barra(motor)`). O corpo traz `status` (`ok`,
`sem_controle`, `sem_endereco`, `sem_perfil`), o `motivo` quando recusa, o `perfil` em que gravou, se
`gravado` de fato (regravar perfil idêntico troca a data do arquivo e faz o daemon reaplicá-lo) e os
`forte_pct`/`fraco_pct` que passaram a valer, que é o que a tela pinta de volta. A tela NÃO digita a
faixa nem o padrão: quem recusa fora de 0-100 é a borda do esquema, e o 100 do «sem opinião» chega no
estado completo do daemon como `rumble_motor_pct_padrao`. O ganho da háptica (`haptica_pct`, 0-200,
O-GANHO-DA-HAPTICA-TEM-DONO-01) vai no mesmo pedido, e o padrão chega como `haptica_pct_padrao`.
`efeito_haptico` e `efeito_imersao` (15/10/2026) são as duas listas da aba Vibração: `do_estilo` apaga
a chave, e a resposta devolve cada uma (o valor ou `do_estilo`).
