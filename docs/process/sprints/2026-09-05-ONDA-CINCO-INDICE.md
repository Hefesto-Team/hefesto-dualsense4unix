---
sprint: ONDA-CINCO-INDICE
estado: absorvida
---

> **ESTADO 06/09/2026: absorvida** — índice ou folha de decisões, não é sprint
> executável; o que ela lista vive nas sprints filhas e no `SPRINT_ORDER.md`.

# ONDA CINCO — as vinte e quatro sprints das 41 decisões dela

> **06/09/2026 — a ORDEM de despacho destas sprints é a de
> [AS VINTE E QUATRO HORAS](../2026-09-06-AS-VINTE-E-QUATRO-HORAS-a-ordem-que-o-orquestrador-despacha-e-as-rotas-corrigidas.md),
> §4 e §5, que substitui as faixas deste índice.** Os frontmatters de dezesseis
> sprints foram corrigidos (uma chave `depois_de`, sem ciclos); nasceu a
> `ONDA5-P-01` (o piloto), e a 10-03 e o `DIVERGENCIAS.md` passaram ao
> coordenador. Fechadas até aqui: 03-01, 04-01, MIC-VIRTUAL-01 passo 1, DOCUMENTACAO.

**05/09/2026.** Ela respondeu **41 decisões** num dia. Onze frentes as leram aba
por aba, mediram o que já existia antes de escrever qualquer coisa, e
devolveram **24 sprints e um documento de princípio**.

O que a medição virou do avesso, e é o placar que abre este índice:

> **Dezessete das 41 já estavam no produto. E SEIS não eram decisão de tela —
> eram DEFEITO, ditas com a palavra dela.**

O laudo decisão a decisão está em
[AS QUARENTA E UMA DECISÕES DELA](../2026-09-05-AS-QUARENTA-E-UMA-DECISOES-DELA.md).
Por que a fila repetiu — as 41 já tinham dono, e onde está o desatualizado —
está em
[POR QUE A FILA REPETE](../2026-09-05-POR-QUE-A-FILA-REPETE-a-queixa-dela-medida.md).

---

## 0. O QUE JÁ FECHOU — 05/09/2026, noite

**Duas das três da FAIXA 0, e a que desbloqueia mais.**

| sprint | o que fechou |
| --- | --- |
| **ONDA5-03-01** | **O campo pisca em verde.** Os cinco passos entraram: a classe `.hef-deu-certo` na folha do módulo (vale nas dez abas sem republicar desenho), o pouso levando o desfecho, o `voltouDoVoo` acendendo e apagando sozinho em `MS_DA_PISCADA = 1500`, e o `"Pronto."` **fora da tela** — a `FRASE_DE_SUCESSO` morreu por não ter mais chamador. A ordem contrária que o piloto carregava por escrito (*"não construa nenhum dos dois"*) foi substituída com a data e a atribuição certa: quem recusou foi o PO, não ela. |
| **ONDA5-04-01** | **O brilho aplica em vez de justificar a falha.** O trilho passa a escrever no aparelho mesmo quando o motor não afirma a cor, e a régua foi INVERTIDA com a razão datada — ela exigia o contrário. |
| **ONDA5-MIC-VIRTUAL-01** | **Passo 1 de dois: o canal ganha o nome do CONTROLE.** `integrations/canal_do_microfone.py` é o dono único de `hefesto_mic_<hex6>` e do ciclo de vida. O mecanismo é REUSADO (`SourceVirtualPipeWire`, de 25/07) e a prioridade é LIDA do dono. **O Passo 2 não entrou de propósito**: ele exige medição na bancada antes do código, e a dívida está declarada no `casa-sabe` com endereço e razão. |

**AS DUAS RÉGUAS DO MICROFONE ACHARAM DEFEITO NA PRIMEIRA EXECUÇÃO**, e uma
delas reprovou a si mesma: `test_a_mascara_nao_alcanca_o_microfone` lia linha a
linha e acusou o módulo novo, que cita o documento do princípio
(`A-MASCARA-NAO-CUSTA-FEATURE…md`) no cabeçalho. Passou a ler por AST — código,
nunca prosa —, e a isenção do comentário sobre bits do `luz_do_mic` morreu junto
por não precisar mais existir. A outra pegou que `so_hex("sem-identidade")`
devolve `"emdedade"`: o canal nasceria batizado `hefesto_mic_dedade` sobre uma
string que não é endereço nenhum.

**As quatro réguas novas da 03-01 mordem em lugares diferentes**, e a quinta
mordida NÃO PEGOU — está declarada: arrancar o `!important` da folha deixa
`test_o_sucesso_calado_pisca_e_nao_fala` verde, porque o `.mudo-i` apagado que
ela clica não declara `border-color` própria. Quem declara são `.mudo-i.on` e
`select.modo`, e nenhum está no caminho daquele clique. O limite está escrito
nos dois arquivos, não esquecido.

**E TRÊS RÉGUAS IRMÃS TIVERAM DE MUDAR DE LEITURA** — o índice dizia que elas
continuariam *"sem uma letra alterada"*, e a medição desmentiu: as três liam o
`depois-do-sucesso`, que é o gesto CALADO, e ele deixou de depositar frase. A
pergunta de cada uma continua inteira; o que mudou é onde há frase para medir
(`com-a-frase-do-dono`). Uma quarta, na aba 09, foi invertida pela mesma razão.

---

## 1. O PLACAR

| | quantas |
| --- | ---: |
| decisões dela nesta carga | **41** |
| sprints escritas | **24** |
| — de **DEFEITO** | **15** |
| — de **DESENHO** | **9** |
| documento de princípio (não é sprint) | **1** |
| decisões que fecharam **sem uma linha de código** | **17** |

**A linha que separa DESENHO de DEFEITO, e ela é dela:**

> **O Hefesto não explica a própria falha — ele a conserta.**

Quando a palavra dela diz *"parece um bug"*, *"não deveria acontecer"*, *"isso
é erro do produto"* ou *"tem que aplicar, não justificar a falha"*, a sprint
**não redige uma frase melhor: ela mede a causa e conserta.** Seis decisões
chegaram assim, e são estas — cada uma com a palavra que a classifica:

| decisão | a palavra dela | a sprint |
| --- | --- | --- |
| **02-Q8** | *"Esse erro não deveria acontecer. Deveria ser só pro controle em questao."* <!-- noqa-acento: citação literal dela --> | [ONDA5-02-01](2026-09-05-ONDA5-02-01-o-microfone-do-vizinho-e-a-porta-que-ficou-aberta.md) |
| **04-Q4** | *"O Hefesto não pode ter essa falha. Isso tem que aplicar, não justificar a falha"* | [ONDA5-04-01](2026-09-05-ONDA5-04-01-o-brilho-aplica-em-vez-de-justificar-a-falha.md) |
| **05-Q6** | *"Parece erro. Não deveria ocorrer ajuste de gambiarra sobre falha de produto nosso"* | [ONDA5-05-02](2026-09-05-ONDA5-05-02-o-clique-que-a-interface-nao-entendia.md) |
| **07-Q1** | *"Deve aplicar automaticamente como era no gtk"* | [ONDA5-07-01](2026-09-05-ONDA5-07-01-a-linha-intocavel-e-aplicada-em-vez-de-explicada.md) · [ONDA5-07-02](2026-09-05-ONDA5-07-02-o-rodape-perdeu-a-carona-que-a-janela-velha-pega.md) |
| **09-Q3** | *"mas o botão tem de realmente fazer o que promete"* | [ONDA5-09-02](2026-09-05-ONDA5-09-02-o-atualizar-nao-diz-pronto-sem-ter-feito.md) |
| **10-Q2** | *"Isso é erro do produto."* | [ONDA5-10-01](2026-09-05-ONDA5-10-01-o-hefesto-nao-manda-ninguem-para-o-terminal.md) |

**São seis pela palavra dela e QUINZE no total**, porque a medição achou defeito
embaixo de decisões que ela deu como escolha de tela — o PS que a emulação nunca
viu, o `⊘` que é porta de mão única, o rodapé do mapa com dois donos. Quem
escolheu a opção não errou: **o produto é que não fazia o que a opção descrevia.**

---

## 2. A ORDEM, E A RAZÃO DE CADA POSIÇÃO

### FAIXA 0 — a infraestrutura: três decisões que valem para as DEZ abas

Estas três não são de aba nenhuma. Enquanto elas não fecharem, quem depende
delas escreve peça que vai divergir — que é exatamente o defeito que a **D-01**
existia para evitar. **Elas correm as três em paralelo: nenhum arquivo em comum.**

| # | o que fecha | a sprint | quem espera por ela |
| --- | --- | --- | --- |
| **0.1** | **O verde do "deu certo"** (03-Q4) — o campo que ela mexeu pisca 1,5 s, sem palavra nova na tela | [ONDA5-03-01](2026-09-05-ONDA5-03-01-o-campo-que-pisca-e-o-numero-do-voo-que-ja-o-endereca.md) | 01-03 (declarado), e 02-02, 04-01, 05-03, 09-01, 09-02 escrevem sobre ela sem construí-la |
| **0.2** | **A fala das duas metades** — quando o aparelho recebeu e o perfil não guardou, a tela diz as DUAS coisas | [AS-DUAS-ABAS-FALAM-01](2026-09-05-AS-DUAS-ABAS-FALAM-01-o-aparelho-recebeu-e-o-perfil-nao-guardou.md) | 03-02 (declarado) |
| **0.3** | **A máscara não custa feature** (10-Q6) — o princípio, o inventário medido, e o canal que falta | [A MÁSCARA NÃO CUSTA FEATURE](../2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md) · [ONDA5-MIC-VIRTUAL-01](2026-09-05-ONDA5-MIC-VIRTUAL-01-o-microfone-do-dualsense-sob-a-mascara-xbox.md) | 10-03, que aponta o princípio ao documento que o possui; e 02-01, que o cita no Passo 2 |

**Por que a 0.1 vem primeiro de todas:** o piloto carrega hoje, por escrito, a
ordem contrária à decisão dela.
`src/hefesto_dualsense4unix/interface/hefesto_vivo.py:2231-2232` diz *"o campo
que pisca, na aba 03, e a faixa embaixo da grade, na 05. **Não construa nenhum
dos dois.**"* — e ela pediu os dois no mesmo dia. **Cinco frentes acharam essa
linha por caminhos independentes** — as das abas 03, 04, 05, 06 e 09 —, o que é
a melhor prova de que ela está no caminho de todo mundo. Enquanto ela não
morrer, cada frente que a ler implementa a decisão morta.

**Por que a 0.3 é infraestrutura e não uma frase de tela:** o corolário dela —
*o Hefesto não explica a própria falha, ele a conserta* — é o critério com que
**toda** frase de limitação deste produto passa a ser julgada. A 02-01 já o usa
como razão de projeto no Passo 2, sem que ninguém tenha combinado isso.

### FAIXA 1 — as que não esperam ninguém

Quinze sprints, e nenhuma delas tem `depois_de` vivo. **Elas não correm todas
juntas:** as seis colisões abertas da §3.2 envolvem NOVE destas quinze, e é lá
que se lê qual espera qual.

`ONDA5-01-01` · `ONDA5-01-02` · `ONDA5-02-01` · `ONDA5-02-02` ·
`ONDA5-04-01` · `ONDA5-05-01` · `ONDA5-05-02` · `ONDA5-06-01` ·
`ONDA5-07-01` · `ONDA5-07-02` · `ONDA5-08-01` · `ONDA5-09-01` ·
`ONDA5-09-02` · `ONDA5-10-01` · `ONDA5-10-03`

### FAIXA 2 — as que esperam, e a §4 diz por quê

`ONDA5-01-03` · `ONDA5-03-02` · `ONDA5-05-03` · `ONDA5-06-02` ·
`ONDA5-07-03` · `ONDA5-08-02` · `ONDA5-10-02`

---

## 3. O QUE CORRE EM PARALELO — DIVIDIDO POR ARQUIVO

**Esta é a seção que decide a leva.** A divisão desta casa é por POSSE DE
ARQUIVO, e duas frentes no mesmo arquivo é conflito garantido — não é hipótese,
é o que a regência de 04/09 mediu.

### 3.1 · Quem possui o quê

| sprint | tipo | os arquivos que ela abre |
| --- | --- | --- |
| **ONDA5-01-01** | DEFEITO | `interface/pacotes/a01_jogar.py` · `tests/unit/test_a01_a_coluna_atencao_acende_o_mais_grave.py` |
| **ONDA5-01-02** | DEFEITO | `app/actions/home_actions.py` · `interface/frases_que_ela_baniu.py` · `tests/unit/test_a_aba_01_jogar_fecha_as_linhas.py` · `tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py` |
| **ONDA5-01-03** | DESENHO | `interface/pacotes/a01_jogar.py` · `tests/unit/test_a_aba_01_jogar_fecha_as_linhas.py` |
| **ONDA5-02-01** | DEFEITO | `daemon/ipc_handlers.py` · `integrations/audio_control.py` · `interface/pacotes/a02_controles.py` · uma régua nova |
| **ONDA5-02-02** | DESENHO | `interface/aba02.py` · `mockup/02-controles.html` · declara em `mockup/DIVERGENCIAS.md` |
| **ONDA5-03-01** | DESENHO | `interface/hefesto_vivo.py` · `gui/ponte_da_tela.py` · `tests/unit/test_o_recado_de_sucesso_pousa_no_cartao.py` |
| **ONDA5-03-02** | DESENHO | `interface/pacotes/a03_gatilhos.py` · `interface/aba03.py` · `tests/unit/test_a_aba_03_gatilhos_fecha_as_linhas.py` |
| **ONDA5-04-01** | DEFEITO | `interface/pacotes/a04_iluminacao.py` · `tests/unit/test_a_04_o_trilho_de_brilho_grava.py` · `docs/data/paridade-gtk-html.csv` |
| **ONDA5-05-01** | DESENHO | `interface/aba05.py` · `mockup/05-vibracao.html` · `tests/unit/test_a_aba_05_vibracao_fecha_as_linhas.py` |
| **ONDA5-05-02** | DEFEITO | `interface/pacotes/a05_vibracao.py` · `tests/unit/test_a05_a_vibracao_aplica_e_fala.py` |
| **ONDA5-05-03** | DESENHO | `interface/pacotes/a05_vibracao.py` · `interface/aba05.py` · `mockup/05-vibracao.html` · `tests/unit/test_a_aba_05_vibracao_fecha_as_linhas.py` |
| **ONDA5-06-01** | DEFEITO | `core/acoes_de_botao.py` · `profiles/manager.py` · `daemon/subsystems/hotkey.py` · uma régua nova |
| **ONDA5-06-02** | DESENHO | `interface/aba06.py` · `interface/pacotes/a06_navegacao.py` · a página 06 publicada · `tests/unit/test_a_aba_06_navegacao_fecha_as_linhas.py` · uma régua nova |
| **ONDA5-07-01** | DEFEITO | `integrations/steam_launch_options.py` · `integrations/sentinela_do_wrapper.py` · `integrations/prontuario_dos_jogos.py` · `interface/desenho_dos_lancadores.py` · `interface/pacotes/a07_lancadores.py` · cinco réguas |
| **ONDA5-07-02** | DEFEITO | `interface/pacotes/rodape.py` · `interface/pacotes/perfil.py` · `tests/unit/test_carona_do_wrapper_01_salvar_repoe_o_que_a_steam_comeu.py` · **uma linha** em `interface/pacotes/a10_perfis.py` |
| **ONDA5-07-03** | DEFEITO | `app/actions/home_actions.py` · `app/actions/jogar/painel.py` · `interface/pacotes/a01_jogar.py` · `interface/jogar_vivo.py` · `tests/unit/test_wrapper_banner.py` · `tests/unit/test_a_aba01_le_o_estado_em_vez_de_cravar.py` |
| **ONDA5-08-01** | DEFEITO | `interface/aba08.py` · `interface/pacotes/a08_conexoes.py` · `mockup/08-conexoes.html` · `mockup/DIVERGENCIAS.md` · a página 08 publicada · `tests/unit/test_a_aba_08_conexoes_fecha_as_linhas.py` |
| **ONDA5-08-02** | DEFEITO | `app/widgets/mapa_da_mesa.py` · `interface/aba08.py` · `mockup/08-conexoes.html` · a página 08 publicada · `tests/unit/test_a_aba_08_conexoes_fecha_as_linhas.py` |
| **ONDA5-09-01** | DESENHO | `interface/aba09.py` · `mockup/09-sistema.html` · `tests/unit/test_a_aba_09_sistema_fecha_as_linhas.py` |
| **ONDA5-09-02** | DEFEITO | `interface/pacotes/a09_sistema.py` · uma régua nova |
| **ONDA5-10-01** | DEFEITO | `profiles/simple_match.py` · `app/actions/perfis_web.py` · `app/actions/profiles_actions.py` · `interface/pacotes/a10_perfis.py` · `interface/aba10.py` · `tests/unit/test_a_aba_10_perfis_fecha_as_linhas.py` |
| **ONDA5-10-02** | DESENHO | `interface/aba10.py` · `interface/pacotes/a10_perfis.py` · `mockup/10-perfis.html` · `app/actions/carona_do_wrapper.py` · `integrations/sentinela_do_wrapper.py` · `tests/unit/test_a_aba_10_perfis_fecha_as_linhas.py` |
| **ONDA5-10-03** | DEFEITO | `docs/data/paridade-gtk-html.csv` — e só |
| **ONDA5-MIC-VIRTUAL-01** | DEFEITO | `integrations/fontes_de_captura.py` · `integrations/quem_ouve_o_microfone.py` · um módulo e duas réguas novos |
| **AS-DUAS-ABAS-FALAM-01** | DEFEITO | `interface/pacotes/a03_gatilhos.py` · `tests/unit/test_o_gatilho_aplicado_vai_para_o_perfil.py` |

### 3.2 · AS DOZE COLISÕES, e as seis que ninguém resolveu

**Dezoito arquivos têm mais de um dono nesta onda, e eles formam ONZE
colisões.** Cinco já estão serializadas por `depois_de` — a colisão se
serializa, não se proíbe. **As outras SEIS não têm ordem nenhuma, e é aqui que
quem coordena decide.**

| arquivo | as sprints | estado |
| --- | --- | --- |
| `mockup/05-vibracao.html` · `interface/aba05.py` · `interface/pacotes/a05_vibracao.py` · `tests/unit/test_a_aba_05_vibracao_fecha_as_linhas.py` | 05-01 · 05-02 · 05-03 | **SERIALIZADA** — 05-03 `depois_de` as duas |
| `interface/aba08.py` · `mockup/08-conexoes.html` · a página 08 · `tests/unit/test_a_aba_08_conexoes_fecha_as_linhas.py` | 08-01 · 08-02 | **SERIALIZADA** — 08-02 `depois_de` 08-01 |
| `interface/aba10.py` · `tests/unit/test_a_aba_10_perfis_fecha_as_linhas.py` | 10-01 · 10-02 | **SERIALIZADA** — 10-02 `depois_de` 10-01 |
| `interface/pacotes/a03_gatilhos.py` | 03-02 · AS-DUAS-ABAS-FALAM-01 | **SERIALIZADA** — 03-02 `depois_de` a outra |
| `tests/unit/test_a_aba_01_jogar_fecha_as_linhas.py` | 01-02 · 01-03 | **SERIALIZADA** — 01-03 `depois_de` 01-02 |
| **`docs/data/paridade-gtk-html.csv`** | **04-01 · 10-03** | **ABERTA** |
| **`mockup/DIVERGENCIAS.md`** | **02-02 (declara) · 08-01 (posse)** | **ABERTA** |
| **`app/actions/home_actions.py`** | **01-02 · 07-03** | **ABERTA** |
| **`integrations/sentinela_do_wrapper.py`** | **07-01 · 10-02** | **ABERTA** |
| **`interface/pacotes/a01_jogar.py`** | **01-01 · 01-03 · 07-03** | **ABERTA** (01-03 já espera 01-01; 07-03 não espera ninguém) |
| **`interface/pacotes/a10_perfis.py`** | **07-02 (uma linha) · 10-01 · 10-02** | **ABERTA** (10-02 já espera 10-01; 07-02 não) |

**A resolução de cada uma das seis, e nenhuma delas custa código:**

1. **`docs/data/paridade-gtk-html.csv` — o CSV tem UM dono por leva, sempre.**
   A `ONDA5-10-03` tem o CSV como posse INTEIRA; a `ONDA5-04-01` só reescreve a
   célula da linha 134. **10-03 é a dona; 04-01 passa a mão** — põe o CSV em
   `nao_toca` e entrega o texto da célula. É o que a 03-02, a 09-01 e a 09-02 já
   fizeram por conta própria: as três listam as linhas que caducam e não abrem o
   arquivo (96, 97, 102, 106, 108, 113 pela 03-02; 314 e 323 pela 09).
2. **`mockup/DIVERGENCIAS.md` — quem coordena escreve as duas seções no fim.**
   O arquivo é declaração, não código, e as duas frentes escrevem seções de abas
   diferentes. Serializar seria caro à toa; escrever ao mesmo tempo é conflito
   por linha.
3. **`app/actions/home_actions.py` — 01-02 primeiro, 07-03 depois.** São funções
   diferentes do mesmo arquivo: a 01-02 mata a frase banida; a 07-03 reescreve o
   aviso do jogo aberto. A 01-02 é pequena (dois arquivos de código) e a 07-03 já
   espera a 07-02 — a ordem sai de graça.
4. **`integrations/sentinela_do_wrapper.py` — 10-02 `depois_de` 07-01.** A 07-01
   possui o arquivo inteiro; a 10-02 só precisa dele para encurtar a frase da
   10-Q5. A alternativa mais barata é a 10-02 entregar o texto curto para a
   07-01 e não abrir o arquivo.
5. **`interface/pacotes/a01_jogar.py` — 01-01, depois 07-03, depois 01-03.** As
   três mexem na COLUNA ATENÇÃO da mesma aba: a 01-01 acrescenta a linha da cura
   do travamento, a 07-03 CALA o aviso do jogo aberto, a 01-03 fecha o cadeado.
   Duas delas mudam a mesma lista de avisos; fazê-las juntas é reescrever a
   coluna duas vezes.
6. **`interface/pacotes/a10_perfis.py` — a linha é da 10-01, e a própria 07-02
   já escreveu isso.** A 07-02 move `_com_a_carona` para o módulo compartilhado e
   deixa uma linha de delegação na a10; a sprint declara, no `toca_uma_linha`:
   *se outra frente desta leva for dona da a10, essa linha é dela.* **É.** A
   10-01 escreve a delegação; a 07-02 relata.

### 3.3 · UMA COLISÃO QUE NÃO É DE ARQUIVO, e por isso não aparece na tabela

**`escolher_fonte` tem dois interessados e um dono.** A função vive em
`src/hefesto_dualsense4unix/integrations/fontes_de_captura.py:192`, que é posse
da `ONDA5-MIC-VIRTUAL-01`. A `ONDA5-02-01` **não** abre esse arquivo — declara-o
em `nao_toca` — mas o Passo 2 dela depende do contrato dele: hoje
`src/hefesto_dualsense4unix/integrations/audio_control.py:368` chama
`escolher_fonte(fontes, uniq, [], usb)`, com a mesa VAZIA, e a cura é passar a
mesa para que a regra 4 volte a valer.

**Se a MIC-VIRTUAL-01 mudar a assinatura, a cura da 02-01 quebra em silêncio.**
Quem coordenar avisa as duas, ou serializa. As duas correm juntas hoje sem
nenhum aviso escrito.

---

## 4. AS ESPERAS DO PLANO, NOMEADAS

| espera | por quê |
| --- | --- |
| **01-03 → 01-01, 01-02, 03-01** | o cadeado já está na tela; o que falta é o verde de 1,5 s, que é peça do piloto (03-01). E os três mexem na aba 01 |
| **03-02 → 03-01** | a metade de ABA da 03-Q4 não existe sem a metade do PILOTO |
| **03-02 → AS-DUAS-ABAS-FALAM-01** | mesmo arquivo: `interface/pacotes/a03_gatilhos.py` |
| **05-03 → 05-01, 05-02** | a 05-03 toca os DOIS arquivos das outras duas |
| **06-02 → 06-01** | a 22ª linha da tabela só pode nascer depois de o `"ps"` existir no motor; a régua viva de hoje afirma o contrário (`tests/unit/test_a_aba_06_navegacao_fecha_as_linhas.py:233`) |
| **07-03 → 07-02** | a frase nova promete *"reponho assim que o jogo e a Steam fecharem"*, e quem cumpre é a vigia — que só nasce de um gesto do rodapé. Enquanto o rodapé não pegar a carona, a frase mente |
| **08-02 → 08-01** | mesmos quatro arquivos da aba 08 |
| **10-02 → 10-01** | mesmos `interface/aba10.py` e `interface/pacotes/a10_perfis.py` |

**As esperas já PAGAS**, que aparecem no `depois_de` de quatro sprints e não
seguram nada: `ONDA2-04-ILUMINACAO-01`, `ONDA2-05-VIBRACAO-01`,
`ONDA1-D1-O-SOM-01`, `CANAL-POR-CONTROLE-01` e `MIC-DA-MESA-ELEICAO-01` — as
cinco fecharam antes de hoje.

**E as esperas que a §3.2 acrescenta**, que não estão em nenhum frontmatter e
por isso não existem para quem só lê o cabeçalho da sprint: **04-01 depois de
10-03** (ou a mão trocada no CSV), **07-03 depois de 01-01 e de 01-02**,
**01-03 depois de 07-03**, **10-02 depois de 07-01** — mais a linha da a10, que
passa da 07-02 para a 10-01, e o `mockup/DIVERGENCIAS.md`, que quem coordena
escreve no fim.

---

## 5. O QUE FICOU ABERTO

As onze frentes declararam o que **não** conseguiram escrever, e a razão. Nada
aqui é esquecimento: é dívida com endereço.

### 5.1 · O que é DELA decidir, e nenhuma sprint pode fechar

| o quê | onde está escrito |
| --- | --- |
| **A palavra do selo novo da coluna Atenção** — **06/09: `CONTROLE`, revisto por ela na publicação** (`D-0609-CURA-USB-ENTRA`). Nenhum dos sete de `ORDEM_DA_GRAVIDADE` (`src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:147-149`) descreve o cabo USB do aparelho, e `RÁDIO` seria mentira — já é o selo do Bluetooth frágil. Selo é texto de tela, logo é dela | ONDA5-01-01 §3 |
| ~~O `↻` de reenvio da aba 03 fica ou sai.~~ **DECIDIDO POR ELA EM 06/09: SAI** — a ONDA5-03-02 ganhou o passo da remoção (`D-0609-REENVIO-SAI`). O que segue é a história: Ela respondeu *"Nada novo"* à 03-Q3 **dezenove horas depois** de o botão nascer (04/09, 20:14). Não se remove trabalho medido, e não se declara aprovado o que ela não viu. A pergunta está pronta na sprint | ONDA5-03-02 §2 |
| **A tinta exata do pino do interruptor sob o portão.** A regra está escrita — *o portão pinta o CONTROLE e nunca encosta no que diz o LADO* —, mas se o verde cheio é demais para um interruptor apagado, quem decide é o olho dela, com as duas fotos lado a lado | ONDA5-06-02 |

### 5.2 · O que espera MEDIÇÃO na máquina, e nenhuma frente pôde medir

Nenhuma das onze executou nada — nem suíte, nem portão, nem produto. Três
afirmações ficaram construídas com cuidado, e não provadas:

* **O custo por tique de `check_snd_quirk`.** Se não couber nos 100 ms do tique,
  a resposta é cachear — **não** deixar a linha de fora (ONDA5-01-01).
* **Se a piscada de 1,5 s sobrevive ao `<input type="range">` da aba 03**, que é
  o único dos cinco campos clicáveis RECRIADO pela pintura, e recriado
  exatamente no tique seguinte ao gesto que deu certo (ONDA5-03-01 §5).
* **Se o `has_extended_ignore` enxerga o próprio veneno quando ele não é o
  primeiro da lista.** A sprint manda escrever o caso ANTES de curar, e sair da
  sprint com a razão se a leitura não se confirmar (ONDA5-07-01, Passo 5).

### 5.3 · O que é de OUTRA posse, e por isso ficou declarado

* **O terceiro `lugar` do depósito de recados.** A 05-Q4 pede que a frase suma
  sozinha na faixa sob a grade; o depósito com prazo é UM só para as dez abas e
  mora no piloto. A `ONDA5-05-03` entrega os passos 1 a 3 e RELATA o 4 com a
  forma exata. **Sem isso a 05-Q4 fica pela metade.**
* **O tom do cartão quando o daemon responde "guardado" ou "nada aconteceu".**
  Falta um segundo retorno dizendo qual dos quatro destinos venceu, e o dono é
  `src/hefesto_dualsense4unix/app/textos_de_aplicacao.py`. Escrever isso dentro
  da aba 04 seria a segunda verdade sobre o mesmo payload (ONDA5-04-01 §5).
* **A metade "ao vivo" da 10-Q4.** O piloto tem três portas de escuta e nenhuma
  é `input`; ligar uma ao mesmo atributo regravaria o perfil a cada tecla. A
  `ONDA5-10-02` relata o desenho e manda escrever na entrega que a tecla-a-tecla
  **não** foi entregue.
* **A colisão do `data-controle`, que é de quatro abas.** O desenho do controle
  carrega `data-controle="dualsense"` (o MODELO) e o piloto usa o mesmo atributo
  para o ASSENTO. Hoje não vira clique na 05, mas todo campo dentro do desenho
  volta com dono errado. A cura mora num arquivo compartilhado (ONDA5-05-02 §4).
* **A metade Steam do `daemon.reload` pode falhar em silêncio**, dentro de um
  `contextlib.suppress`. A cura é do daemon (ONDA5-09-02 §2).
* **`src/hefesto_dualsense4unix/daemon/lifecycle.py:3405` ganharia com a mesa** —
  é melhora, não defeito, e o arquivo é lido também pela janela GTK (ONDA5-02-01).

### 5.4 · O que não veio na carga, e continua aberto

* **As duas dívidas da ONDA2-08, e a primeira PERDE TRABALHO DELA:** o ouvinte de
  `blur` no piloto — ela digita o apelido do adaptador num `contenteditable`, que
  não dispara `click` nem `change` ao perder o foco, e o nome se perde; e o
  registro do gesto de renomear nas listas de proteção, sem o qual a régua
  continua cega para toda escrita que passe pelo BlueZ. As duas estão em
  `docs/process/agentes/2026-09-04/ONDA2-08.md`.
* **A decisão [06] de 04/09** (o botão travado apaga e o motivo vira um `?`) não
  veio nesta carga e toca `interface/aba08.py` — se for despachada, entra em
  **fila** com a ONDA5-08-01, não em paralelo.
* **O caminho do giroscópio até o jogo sob a máscara Xbox.** O canal próprio
  existe. **FATO SUBSTITUÍDO em 13/09/2026:** o zero em Modo Virtual era da
  libSDL2 2.30.0 do sistema; nas bibliotecas dos runtimes da Steam o vpad expõe
  os dois sensores, e o SDL pareia o nó «Motion Sensors» pelo `uniq` (a tabela
  está na
  [SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md),
  §1). Sob a máscara Xbox a rota continua sem medição: a sprint que nascer disso
  tem de MEDIR antes de prometer. Escrever passos sem essa medição seria o
  defeito que o princípio existe para matar.
* **A `ONDA5-MIC-VIRTUAL-02`** (o mesmo canal, no rádio) está declarada por ID
  dentro da 01, com o corte e a razão: o cabo tem rede embaixo, o rádio não.
* **Os três presets órfãos** (navegador, terminal, editor) seguem sem casa por
  uma contradição entre duas decisões dela do MESMO dia —
  `docs/data/decisoes-dela.csv:55` fecha em cinco perfis e `:84` diz cinco mais
  "Programas" —, sem lápide dizendo qual caducou. A ONDA5-10-01 cria a régua que
  os DECLARA em vez de os esconder.
* **O carimbo de ponte** (qual ponte já funcionou naquele jogo) continua sem
  lugar na tela; nenhuma das quatro respostas da 10-Q4 o endereça.

---

## 6. ANTES DE FECHAR QUALQUER SPRINT DESTA ONDA

```bash
git add -A                       # os portões são cegos a arquivo novo
bash scripts/portoes.sh          # sem argumento; o --rapido não roda os que pegam isto
```

**E a validação de tela, que não é opcional quando o trabalho toca a interface:**
foto `--oculta` antes e depois, **o clique**, e **a mordida**. Ela tem UMA tela.
O contrato está em [COMO-OLHAR-A-TELA.md](../COMO-OLHAR-A-TELA.md); a palavra
final sobre pixel é dela
([PROVA-DE-TELA-01](2026-07-27-PROVA-DE-TELA-01-dez-minutos-de-olho-antes-de-qualquer-leva.md)),
e o papel de quem reger a leva está em
[COMO-COORDENAR-UMA-LEVA.md](../COMO-COORDENAR-UMA-LEVA.md).

**Duas coisas que quem coordenar precisa saber antes de despachar:**

1. **As dez páginas publicadas são hoje byte a byte idênticas ao mockup** —
   medido em 05/09/2026 comparando `mockup/NN-*.html` com as dez de
   `src/hefesto_dualsense4unix/interface/paginas/`. Quem mexer na bancada
   quebra essa igualdade de propósito, e a republicação é **ato dela**.
2. **A onda 3 fechou hoje e deixou 24 testes vermelhos**, cujas famílias estão em
   [ONDE PARAMOS · a onda três](../2026-09-05-ONDE-PARAMOS-a-onda-tres-e-as-reguas-que-mediam-o-mundo-de-ontem.md).
   **Eles não são desta onda** — mas quem rodar a suíte vai encontrá-los, e é
   melhor saber disso antes do que depois.
