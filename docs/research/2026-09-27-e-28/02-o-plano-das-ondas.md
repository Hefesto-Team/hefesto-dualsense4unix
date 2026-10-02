# O plano das ondas de 28/09: as sprints abertas em sete ondas e o que se conferiu nele

Como as sprints abertas de 26 a 28/09/2026 foram postas em ondas por posse de arquivo e por dependência lógica, o que a conferência derrubou no plano e o que se preparou antes do primeiro despacho (madrugada de 28/09/2026).

## O problema

As sprints abertas escritas de 26 a 28/09 eram 38. O levantamento de antes as punha em 18 camadas, quase todas por posse: duas sprints que mexem no mesmo arquivo não andam juntas. A pergunta era o **menor número de ondas**, separando dois tipos de dependência:

- **lógica**: B usa o que A cria, ou muda o comportamento que A cura;
- **só de posse**: as duas tocam o mesmo arquivo, e a colisão se desfaz com uma **cessão** (uma sprint cede o arquivo a outra numa onda e mexe nele na seguinte).

A regra de cada onda: nenhum arquivo, nem prefixo de pasta declarado, com dois donos.

A ordem tinha três pontos fixos. A `O-MODO-XBOX-NAO-E-QUEDA-02` vai na primeira onda, porque é a cura que a pessoa sentiu na mão em 27/09. A `NO-MODO-XBOX-TUDO-FUNCIONA-01`, a maior de todas, vai o mais cedo que a lógica deixar. As varreduras que atravessam `src/` e `scripts/` inteiros vão no fim, quando o código parou de mudar: `O-CODIGO-SEM-NARRADOR-01`, `AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA-01`, `AS-REFERENCIAS-DA-FERRAMENTA-SAEM-DA-MESA-01` e `O-CODIGO-NAO-NOMEIA-A-FERRAMENTA-01`.

## O plano: sete ondas

Cada sprint ganhou uma classe: **código** (código e régua, sem a mão dela), **código + prova no aparelho** (o código anda e a prova fica para a mão dela), **fora do repositório** (ganchos da máquina, escritos numa cópia de ensaio e instalados juntos no fim) ou **para antes do gesto dela** (prepara e para antes do que é dela: o push forçado da reescrita, a remoção do aplicativo instalado no GitHub). O tamanho vai de P (menos de 1 h) a GG (mais de 4 h).

| onda | o que anda | a razão |
|---|---|---|
| 1 | `O-MODO-XBOX-NAO-E-QUEDA-02` (G), `NO-MODO-XBOX-TUDO-FUNCIONA-01` (GG), `O-SALVAR-E-O-APLICAR-LEEM-O-PERFIL-01`, `O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01` (GG), `O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01`, `VERDE-NAO-E-PROVA-01`, `O-ENGASGO-SE-CURA-PELO-QUE-CHEGA-AO-JOGO-01`, `A-DESCOBERTA-LE-O-SYSFS-E-NAO-ABRE-O-NO-01`, `A-RAIZ-SO-COM-O-PRODUTO-01`, `A-CAIXA-FICA-ONDE-ELA-ABRIU-01`, `O-PUSH-SO-COM-O-RECIBO-DOS-PORTOES-01`, a parte (e) da `A-TRAVA-DA-MAQUINA-DELA-01` e a antiga `O-CI-DA-DEV-VOLTA-A-VERDE-01` | a -02 por decisão; a NO-MODO-XBOX junto, porque a posse é disjunta e o código não usa nada que a -02 cria (as duas sobem no mesmo install); a parte (e) da A-TRAVA se aplica antes do despacho, porque a A-RAIZ depende dela |
| 2 | `O-FREESTYLE-E-UMA-CAMADA-SO-01`, `A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01`, `A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01`, `O-BASICO-MEDIDO-01` (GG), `O-PRODUTO-EM-QUALQUER-MAQUINA-01` (GG), `TODO-PROGRAMA-DO-DAEMON-NASCE-FORA-DO-SERVICO-01`, `A-ENTRADA-TEM-UM-REGISTRO-SO-01`, `O-README-E-OS-TEXTOS-DE-GENTE-01`, `AS-PAGINAS-DE-PAINEL-SAEM-DO-GIT-01` e o resto da VERDE | as que leem o que a onda 1 cria (o dono do modo, o leitor único do som, o `o_modo_no_ar`, a raiz nova), e as que esperavam um arquivo ocupado na onda 1 (o `hotkey.py`, o `a08_conexoes.py`) |
| 3 | `O-CODIGO-NAO-NOMEIA-A-FERRAMENTA-01`, `AS-PAGINAS-DE-USO-FALAM-COM-QUEM-USA-01`, os restos da O-BASICO e da O-PRODUTO, e, em cópia de ensaio, a `A-TRAVA-DA-MAQUINA-DELA-01` (partes a e c) e a `A-VIGIA-DAS-TRAVAS-01` | o código de produto parou na onda 2 |
| 4 | `A-AUTORIA-SE-MEDE-PELA-LISTA-DE-QUEM-PODE-01`, o resto da USO, e os ganchos `O-DESPACHANTE-DAS-REGRAS-DA-CASA-01`, `O-RASTRO-BARRADO-NO-ATO-01`, `OS-GANCHOS-DO-GIT-NAO-ENSINAM-O-CONTORNO-01` | a régua da autoria só fica verde com o nível 1 da NAO-NOMEIA zerado na ponta |
| 5 | `O-CODIGO-SEM-NARRADOR-01` (GG), sozinha no repositório; os ganchos `A-SENHA-SO-PASSA-PELO-ASKPASS-01`, `O-ENDERECO-NUNCA-CHEGA-A-CONVERSA-01` e `A-ARVORE-TEM-UMA-SESSAO-SO-01` | a varredura mede o texto final |
| 6 | `AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA-01` (parte 1), `O-FEITO-SO-COM-A-PROVA-01` e `A-GUARDA-FECHA-A-PORTA-01` (esta para antes do gesto dela) | toda sprint anterior pode apagar texto que cita commit |
| 7 | `AS-REFERENCIAS-DA-FERRAMENTA-SAEM-DA-MESA-01`, `A-HISTORIA-REESCRITA-UMA-VEZ-SO-01` e `O-GITHUB-SEM-RASTRO-FORA-DO-GIT-01` | refs limpas antes da reescrita; a reescrita para antes do push forçado, e os rulesets só depois dele |

A `A-GUARDA-FECHA-A-PORTA-01` não se instala pela leva: quem arma a trava é ela, no terminal dela, porque uma trava armada por quem ela vigia é uma trava que esse mesmo processo desarma.

### As dependências lógicas que decidem a ordem

- A -02 vem antes da `A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01`, porque o item 3 desta lê o dono do número do jogador que a -02 cria. Vem antes também da `O-FREESTYLE-E-UMA-CAMADA-SO-01`, porque o Freestyle carrega o `mode.caminho` e a prova 5 é o modo sobreviver ao connect.
- A `O-SALVAR-E-O-APLICAR-LEEM-O-PERFIL-01` vem antes da FREESTYLE. Com o Freestyle ligado, o gesto grava nele; sem um Salvar que lê só o perfil, o estado do aparelho viraria escolha gravada.
- O leitor único do som (`O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01`) vem antes da háptica pelo rádio e da `O-BASICO-MEDIDO-01`. A `O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01` também vem antes da O-BASICO, porque a O-BASICO importa o `o_modo_no_ar`.
- A `A-RAIZ-SO-COM-O-PRODUTO-01` vem antes da README e das páginas de uso: o README cita a raiz nova, e a página do Bluetooth liga para `docs/usage/bluetooth-varios-adaptadores.md`, que a A-RAIZ cria.
- A parte (e) da `A-TRAVA-DA-MAQUINA-DELA-01` vem antes da A-RAIZ. Os padrões só saem do `.gitignore` com o ignore global e o `info/exclude` comum já no lugar.
- A reescrita da história nasce da ponta final: depois da parte 1 da CITACOES, com a autoria verde e as refs já limpas.

Três ligações ficam **só na prova**, e o código anda junto:

- A háptica pelo rádio mede a saída pelo uhid já drenado pela A-ENTRADA.
- A prova do fecho da `O-PRODUTO-EM-QUALQUER-MAQUINA-01` é o retrato da O-BASICO numa VM; as duas andam na mesma onda.
- O orçamento de rádio (item 1 da A-ENTRADA) só se mede com a háptica instalada, e por isso sai da leva.

## O que a conferência derrubou

O plano tinha **41 colisões e uma violação de `nao_toca`**. O verificador do próprio plano dava zero por três motivos: lia um levantamento de posse das 01h17, não olhava o `nao_toca` e não conhecia a sprint de 28/09. Um verificador novo, com o frontmatter real de cada sprint, deu **0 colisões para as 39 abertas** depois das dez correções. A mordida foi desfazer três correções: ele acusou 11 colisões e saiu com rc=1.

As dez correções:

1. **Uma sprint ficou fora.** A `O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01`, escrita à 01h23 de 28/09, trata do toque fantasma no botão do microfone, que grava o perfil e muda o microfone padrão. Na onda 1 ela colidia com a SOM no `luz_do_mic.py`. Entra na onda 2 com os itens 1 a 3, e o item 4 (`loader.py`) fica para a onda 3.
2. **A O-FEITO recebeu um arquivo que declara não tocar**: um gancho de fora do repositório que é da O-ENDERECO.
3. **Faltava posse à -02.** O primário é escolhido em `_recompute_primary` (`src/hefesto_dualsense4unix/core/backend_pydualsense.py`), pela «1ª chave de inserção». Esse arquivo e o `daemon/subsystems/poll.py` entram na onda 1. O item 5 (o PS em **qualquer** controle, não só no que acende o «1») precisa do `hotkey.py` e vai para a onda 3.
4. **O CI do `dev` estava vermelho**, e a `O-CI-DA-DEV-VOLTA-A-VERDE-01` não era «só ler». A corrida 36359321758, sobre `108922578`, deu:
   - 35 falhas e 6 erros no Pytest unit, no 3.12 e no 3.11;
   - o job do GTK real vermelho;
   - o job do 3.10 em andamento havia mais de cinco horas.

   Eram 19 arquivos de teste vermelhos, e só um tinha dono no plano. A triagem dividiu assim:

   | quem cura | os vermelhos |
   |---|---|
   | ENGASGO | os dois do uninstall, a aba 09 e os 6 erros do botão do Vulkan |
   | -02 | o do ciclo de vida do daemon |
   | SALVAR | a recusa da aba 06 |
   | VERDE | três da classe dela |
   | TODO-PROGRAMA | dois do `gesto_de_pareamento.py` |
   | O-CI | o resto e o `ci.yml` |

   Com isso, o CI verde só fecha no fim da onda 2.
5. **A NO-MODO-XBOX e a `ROTEADOR-DE-ENTRADA-01` eram a mesma cura.** A ROTEADOR foi absorvida. O giroscópio em mira já existia; no Xbox só se confere que vale. O touchpad e o acelerômetro como fonte esperam o mapa de fontes e destinos, que é decisão dela, e viram entrada condicional na onda 3.
6. **Faltava posse à FREESTYLE**: os leitores do `autoswitch_locked` que ela substitui, que são `state_store.py`, `lifecycle.py`, `ipc_bridge.py`, `home_actions.py`, `a10_perfis.py` e `connection.py`.
7. **O mascarador que a O-BASICO exige não tinha sprint.** Sem ele, «nenhuma linha sai verde». Nasceu a `O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01`, na onda 2.
8. **As cessões só existiam no plano.** Das 41 colisões, 13 eram cessões que o frontmatter não dizia, e quem implementa lê o frontmatter.
9. **Três contratos na mesma onda**, com código em comum e nenhum arquivo em comum:
   - -02 × NO-MODO-XBOX: as assinaturas de `make_virtual_pad` e `quer_uhid` ficam congeladas;
   - -02 × DOCTOR: as chaves do `state_full` não mudam de nome;
   - O-BASICO × mascarador: o nome e a assinatura ficam escritos na sprint.
10. **Arquivos ignorados pelo git estavam na posse de sprint.** Eles não viajam no cherry-pick e têm de ser copiados de volta à árvore principal.

Quatro dependências que o plano chamou de «só de posse» eram lógicas:

- A O-CI é lógica para as demais na prova, que é o CI verde.
- A A-ENTRADA-DE-CADA é lógica para a NO-MODO-XBOX na prova.
- A -02 é lógica para a NO-MODO-XBOX na interface.
- A ROTEADOR era a mesma cura.

**Resta validar depois do plano:**

- As três sprints de háptica em espera ficam velhas com a `A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01`.
- A série O-ASSENTO e a STEAM-NO-FISICO têm de ser validadas de novo depois do item 4 da -02.

## O preparo antes do despacho

**A sprint do mascarador.** A sprint decide um dono só, `src/hefesto_dualsense4unix/core/formas_do_endereco.py`. Ele expõe `mascarar(texto, conhecidos=())`, `mascarar_endereco(valor)`, `formas_do_endereco(octetos)` e a forma pública do serial. A O-BASICO chama só `mascarar`. A escrita da sprint achou mais do que o índice da auditoria contava:

- Os mascaradores do produto são **seis**, e não cinco: o sexto é `integrations/ar_do_adaptador.py`.
- Três deles devolvem o valor cru quando não o reconhecem.
- O `battery_journal` pega os dígitos hex de qualquer texto, quando a regra da casa é descartar o valor.
- O endereço do pad virtual continuava reversível mesmo com o 4.º e o 5.º octetos zerados, porque sobram uns dois candidatos. A sprint decide zerar os quatro bytes do hash.
- Uma régua que reconfigure o structlog global repetiria a cicatriz de `tests/unit/test_reserva_do_posto_01_os_eventos_falam.py:74-90`. A régua 4 embrulha um logger num buffer em vez disso.

A máscara do serial também passa a ter o produto como dono, como pede a resposta 13 dela: «a tela mostra inteiro; o Copiar leva mascarado».

**As cessões escritas no frontmatter.** Foram 31 arquivos de sprint, cada mudança com nota datada de 28/09:

- a posse e o `nao_toca` de quem cede;
- o `depois_de` na ordem das ondas;
- a posse da -02 e da FREESTYLE ampliada;
- a ROTEADOR marcada absorvida;
- a O-CI com a posse de 25/09 (152 arquivos, já no `dev`) trocada pela da onda 1.

Três sprints paradas colidiram com a posse ampliada e ganharam `depois_de`. O verificador de colisão fechou com rc=0: 937 sprints anotadas, 61 abertas (eram 62 antes da absorção) e 20 sem frontmatter de posse, uma dívida que não reprova. Houve duas mordidas: tirar as 6 arestas novas e desfazer 6 cessões deram 6 colisões cada, com rc=1.

## O que ficou aberto

- **Posse ainda não remedida**:
  - os cinco leitores da SOM;
  - as 44 listas de exceção (em 38 arquivos) e os vermelhos da VERDE;
  - os vermelhos da ENGASGO e da SALVAR;
  - o `hotkey.py` e os dois `steam_*` da TODO-PROGRAMA;
  - o `schema.py`, o mapa de canais e a entrada condicional da NO-MODO-XBOX;
  - o `canal_do_microfone.py` da A-ENTRADA.
- **Dependências lógicas ainda não aplicadas no frontmatter**: O-REGISTRO → O-BASICO, e TODO-PROGRAMA → VERDE/O-CI.
- **Corpos com texto antigo**: o B6 da O-PRODUTO e o item 1 da A-ENTRADA ainda descrevem o que foi cedido.
- **Uma frase de mordida fica órfã**: a da régua do diário mascarado, em `tests/unit/test_a_09_sistema_em_tres_secoes.py`, passa a citar uma constante que deixa de existir no `a09_sistema.py`.
- **A ROTEADOR pedia para vir depois da DSU**, e isso tem de ser conferido antes da onda 3.
- **Sprints que a auditoria pede e ninguém escreveu**: o destino, as camadas e o aplicar, antes da FREESTYLE. O plano segue o arquivo da sprint, revisto pela palavra dela de 27/09.
- **O que depende de outros**:
  - de um mantenedor: o passo 10 da A-RAIZ, o secret da autoria, o escopo da reescrita e os rulesets;
  - dela: os gestos de prova, o diff dos dotfiles e do self-heal, a senha, a remoção do aplicativo instalado no GitHub e armar a guarda.
- **Os derivados se regeram na costura de cada lote**: `docs/specs.html`, as contagens do `docs/data/LEIA-PRIMEIRO.md` e as fotos. Sem isso, as réguas de frescor reprovam a integração.
