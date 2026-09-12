# A língua desta casa — o glossário que a tela e o código falam

**06/09/2026.** Pedido dela: *"pode cuidar da documentação completa do projeto
também? pra sempre falarmos a mesma língua?"* — e, no mesmo dia, o motivo:
*"Falei do termo mesa que é horrível. Mas os claudes anteriores entraram na pira
de usar isso em tudo no layout. O termo sai e coloca-se termos simples pro user
comum. feature fica."* <!-- noqa-acento: citação literal dela -->

**Uma palavra, um significado, e dois registros:** o que a TELA diz (para ela
e para qualquer usuária) e o que a CASA diz (código, sprints, commits). Quando
os dois divergem, a coluna da tela manda no texto de tela, e a da casa manda no
nome de arquivo e de função. **Texto de tela não inventa termo: ele vem do
dono** (`app/actions/*`, `app/textos_de_aplicacao.py`), e o que não está aqui
se acrescenta aqui antes de entrar na tela.

## 1. O aparelho e a ligação

| na tela | na casa | o que é |
| --- | --- | --- |
| **controle** · **P1…P4** (jogador) | `controle`, `assento` (`p1`..`p4`), `uniq` (o endereço, nunca na tela) | um DualSense na mão de alguém; o número é o assento, não o aparelho |
| **cabo** · **rádio** | `usb` · `bt` (chave crua); a palavra vem de `home_actions.palavra_do_transporte` | por onde o controle fala com a máquina. A contagem do topo (`2 USB · 0 BT`) é a única exceção, decidida em 06/09 |
| **os controles** · **todos** · **P1 e P2** | `mesa` (só como nome interno: `mesa_viva.py`, `app/mesa.py`) | **"mesa" não entra em texto de tela.** Decisão dela, 05/09 e 06/09: a palavra sai, a feature fica |
| **serviço** | `daemon`, `hefesto-dualsense4unix.service` | o que roda por trás, fala com o aparelho e responde à janela |
| **barra de luz** · **luzes de jogador** · **luz do microfone** | `lightbar`, `player_leds`, `mute_led` | as três luzes do DualSense |
| **gatilho** (L2/R2) · **efeito** | `trigger`, `TriggerEffect` | o gatilho adaptativo e o que ele faz na mão |
| **vibração** · **motor forte / fraco** · **degrau** (Economia · Balanceado · Máximo) | `rumble`, `weak`/`strong`, `orcamento` | a força; o degrau multiplica a barra de cada motor |
| **microfone** · **alto-falante** · **fone** | `mic`, `speaker`, `jack` | o áudio do controle; o mic tem UM ato: ligar e ser ouvido no canal dele |
| **Alto-falante do Controle N** · **Microfone do Controle N** | `alto_falante_bt.nome_do_sink` (`hefesto_som_<hex6>`) · `canal_do_microfone.nome_do_canal` (`hefesto_mic_<hex6>`) | **o rótulo do nó na lista de som do SISTEMA**, um par por controle. Decisão dela, 09/09 (*"4a"*): o número é o **assento** (P1…P4), como na tela — não o aparelho. O nome interno segue o aparelho e não muda de transporte; o rótulo segue o assento. **O endereço nunca entra no rótulo** |
| **giroscópio** · **acelerômetro** · **touchpad** | `gyro`, `accel`, `touchpad`, `sensor_hub` | o movimento e o toque |

## 2. O que ela escolhe

| na tela | na casa | o que é |
| --- | --- | --- |
| **Status: Ligado / Desligado** | `gamepad_emulation.enabled` | o Hefesto no meio, ou fora |
| **Modo**: *Jogar pelo Hefesto* · *Conexão Nativa (Sony)* · *Controlar o PC* · *Não mexer no modo* | `mode_kind`, `native_mode`, `mouse_emulation` | como o controle chega ao jogo. Os quatro rótulos são dela (06/08) |
| **O controle é visto como**: *DualSense* · *Xbox 360* · *Nintendo Pro* | `flavor`, `mascara` | como o JOGO vê o controle. **A máscara não custa feature** (10-Q6): o Hefesto constrói o mecanismo, não descreve a limitação |
| **perfil** · **Personalizado** (o padrão) | `Profile`, `personalizado.json`, `active_profile` | o arquivo com o que ela tocou; **clicar já aplica e já grava** (D1/D2), e cinco coisas ficam globais (D3) |
| **Estilo de Jogo** | `estilos_de_jogo/` (receitas), motor a construir | gatilho + vibração + luz prontos para um tipo de jogo. **Não é perfil**: ação, aventura, corrida saem da lista de perfis (06/09) |
| **Funciona em** (o ambiente do perfil) | `match`, `simple_match`, `steam_app_<id>` | quando o perfil entra sozinho: um jogo, uma janela, todos |
| **atalho de inicialização** | `hefesto-launch`, o wrapper, `LaunchOptions` | a linha que faz o jogo enxergar o controle pelo Hefesto; **reposta de carona** ao Salvar/Aplicar |
| **Steam Input** | `steam_input`, allowlist | o que a Steam põe entre o controle e o jogo; o Hefesto desliga e marca "este jogo não funciona" |

## 3. O que a tela responde

| na tela | na casa | regra |
| --- | --- | --- |
| **piscada verde** (~1,5 s no campo) | `hef-deu-certo`, `MS_DA_PISCADA` | "deu certo" sem palavra nova (03-Q4) |
| **recado** no cartão, **laranja 30 s** | `recusa`, `RuntimeError` do gesto | o aparelho NÃO recebeu; a frase é do dono do assunto |
| **recado** no cartão, **verde 6 s** | `sucesso` com `recado` | deu certo E há notícia (as duas metades: *o aparelho recebeu · o perfil não guardou*) |
| **coluna Atenção** (até 3, `+N`) | `AVISOS_DA_TELA`, `ORDEM_DA_GRAVIDADE` | só o que pede ação; boa notícia não é Atenção |
| **apagado** (botão cinza que ainda responde) | `.apagado`, `razoes_do_cinza` | "não dá para mexer agora", com a razão no `?`; nunca "está desligado" |
| **?** (a dica) | `title`, `data-hef-atributo="title"` | a explicação mora aqui; a tela não explica em linha |
| **dizer as duas metades** | `AS-DUAS-ABAS-FALAM-01` | quando meio ato deu certo, a frase diz o que deu e o que não deu |

**Proibido em texto de tela:** `env`, `vdf`, `uinput`, `hidraw`, `MAC`, `uniq`,
`wrapper_used`, `dedup`, "mesa", "janela do aplicativo", "linha de comando",
`reconciliad`, `compactada`,
qualquer frase que mande a pessoa procurar um botão ou uma janela que não
existe, e qualquer alarme sem medição (`frases_que_ela_baniu.py`).

**ESTA LINHA É O DONO DA LISTA — 11/09/2026, F5-A-REGUA-LE-O-GESTO.** Até esta
data ela era prosa: `frases_que_ela_baniu.PALAVRAS_BANIDAS` tinha três palavras
e o glossário tinha onze proibições, e foi por essa fresta que `uinput`
sobreviveu na dica da Navegação. Agora as duas listas se medem uma contra a
outra, **nos dois sentidos**, em
`tests/unit/test_a_palavra_mesa_nao_chega_a_tela.py`. Palavra nova entra AQUI
primeiro; a tupla do módulo é a cópia que o produto instalado carrega, porque o
pacote não leva `docs/` junto. As duas últimas são raiz e não palavra inteira —
`reconciliad` cobre *reconciliados* e *reconciliadas* sem tocar o verbo
`reconciliar`, que é português vivo em código e em prosa (decisão dela, 09/09,
JOGAR-02 §5). Os dois trechos de FRASE proibida continuam sem forma de palavra,
e por isso ficam de fora da conta.

## 4. A casa (não aparece na tela)

| termo | o que é |
| --- | --- |
| **piloto** | `interface/hefesto_vivo.py`: a janela GTK com o `WebKit2.WebView` que pinta o HTML dez vezes por segundo (**tique** = 100 ms) |
| **pacote** | `interface/pacotes/aNN_*.py`: o que cada aba manda ao piloto por tique, e os **gestos** que ela responde |
| **gerador** · **bancada** · **publicado** | os geradores `aba01.py`…`aba10.py` de `interface/` escrevem `mockup/` (a bancada, o que ela olha); `scripts/check_o_desenho_aprovado.py --publicar NN` leva a `interface/paginas/` (o produto). **Publicar é ato dela** |
| **campo** · **gesto** · **alvo** | `data-campo` (onde o piloto escreve), `data-gesto` (o que o clique chama), `data-hef-alvo` (como escreve: texto, classe, atributo, marcado…) |
| **dono** | o único lugar que sabe um fato ou uma frase; a tela LÊ do dono, nunca redigita |
| **motor** | `app/actions/*`, `app/widgets/*`, `daemon/`: o que a janela GTK usava e a nova reusa. **A janela GTK saiu; o motor fica** |
| **portão** · **régua** · **mordida** | `scripts/portoes.sh` (43); um teste; arrancar a cura e ver a régua reprovar |
| **lápide** · **nota datada** · **fato substituído** | decisão medida que caducou ganha data; número errado é trocado em todos os lugares |
| **estado** de uma sprint | `aberta` (vale e se despacha) · `feita` (entrou, com prova) · `absorvida` (o que falta vive em outro lugar) · `caducou` (a premissa morreu). Está no frontmatter; `check_colisao_de_sprints.py --abertas` é a lista viva |
| **sprint** · **onda** · **leva** · **costura** | uma posse de arquivos com passos e mordidas; sprints paralelas por posse; a leva é o dia; costurar é integrar em `onda/atual` |
| **PO / orquestrador** · **agente** · **coordenador** | quem decide e despacha (o Opus, por delegação dela); quem executa UMA sprint numa worktree; quem costura e roda a suíte |
| **a tela dela** | uma só. Toda janela de teste nasce `--oculta` ou no workspace `OS` |

## 5. Como este arquivo se mantém

* termo novo na tela → linha aqui antes, com o dono;
* termo que ela recusou → some da tela em TODOS os lugares no mesmo dia
  (`scripts/check_regua_de_tela.py` e `frases_que_ela_baniu.py` são os portões
  que já existem). **A palavra "mesa" ENTROU em 06/09/2026**
  (A-PALAVRA-MESA-SAI-01): ela mora em `frases_que_ela_baniu.PALAVRAS_BANIDAS`,
  numa tupla à parte porque palavra se casa por BORDA — `"mesa" in texto` casa
  com *remessa* e com todo nome que a carrega. A régua é
  `tests/unit/test_a_palavra_mesa_nao_chega_a_tela.py`, e o instrumento para
  procurar a próxima é `interface/olhar.py --palavra <palavra>`. **O nome
  interno não se toca** — a borda ignora o que está colado a `-`, `_` ou `.`, e
  o que está dentro de `<code>` é identificador, não palavra de tela;
* o portão `acentuacao` vale aqui como em todo lugar.
