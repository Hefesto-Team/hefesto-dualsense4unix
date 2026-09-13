---
sprint: PERFIS-TIRA-BUSCA-ATIVO-01
estado: absorvida
onda: A-FILA-DE-1309
posse:
  PERFIS-TIRA-BUSCA-ATIVO-01:
    - src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py
    - src/hefesto_dualsense4unix/interface/aba10.py
    - src/hefesto_dualsense4unix/app/actions/profiles_actions.py
    - mockup/10-perfis.html
    - src/hefesto_dualsense4unix/interface/paginas/10-perfis.html
cria:
  - tests/unit/test_a_aba_perfis_segue_o_perfil_que_vale.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py
  - src/hefesto_dualsense4unix/profiles/manager.py
---

# PERFIS-TIRA-BUSCA-ATIVO-01 — a frase que não devia aparecer, a lupa que não filtra, o ↻ em dobro e o perfil que não acompanha

> **ESTADO 13/09/2026 (tarde): absorvida.** O §1 ao §4 fecharam (abaixo). O
> §4.1 entra na
> [VAO-DO-ESQUELETO-01](2026-09-11-VAO-DO-ESQUELETO-01-a-faixa-vazia-de-tres-paginas-e-a-decisao-de-27-08.md),
> que escreve o mesmo `topo.html` e regera as dez páginas no mesmo gesto: o
> literal tem UMA fonte, o `pa-nome` do `topo.html`, e curar só a página 10 não
> existe como caminho (triagem das abertas, 13/09).
>
> **O que era, antes da absorção — ABERTA por um item só, o §4.1.**
>
> * **§1 (a tira) fechou** no commit `fix(tela): a tira da aba Perfis para de
>   falar`: `perfis.desfecho` recebe vazio em todo gesto, e a frase vai ao
>   `interface.log` como `[desfecho]` e à régua como `relato`. Medido no piloto
>   oculto: a tira fica «—» com altura 0 depois do ↻, do clique na linha e 6 s
>   depois.
> * **§2, §3 e §4 fecharam em `71c69c57`.** A causa das três queixas não era a
>   aba: era a janela CONGELADA pela guarda de palavra banida levantando no
>   tique, que deixava na tela o literal do mockup. O ↻ em dobro saiu da página.
> * **§4.1 não fechou:** o chip «Perfil ativo» nasce «Mortal Kombat» nas DEZ
>   páginas publicadas. O literal é do `topo.html`, que está na posse da
>   ALTURA-DA-VISTA-01 (entregue em `87de2f54`, não costurada).

**13/09/2026, madrugada.** Ela abriu a aba Perfis com dois controles (P1 no
cabo, P2 no rádio) e mandou, em três mensagens seguidas:

> *"essa frase de interface que aparece na aba perfil nao devia aparecer nunca.  preciso que faça uma sprint pra corrigir isso tambem."* <!-- noqa-acento: citação literal dela -->
>
> *"fora que o botao pŕocurar na aba perfil nao tá funcionando. e o botao atualizar tá aparecendo duplicado na interface"* <!-- noqa-acento: citação literal dela -->
>
> *"memsmo ativando outro perfil ele fica preso ao anterior na interface ao inves de mostrar o perfil ativo"* <!-- noqa-acento: citação literal dela -->

A frase, como estava na tira:

```
Perfil ativado: Future Knight — Aplicado, menos: luzes, gatilhos, button_actions. · 2 jogos nunca receberam as Opções de Inicialização do Hefesto na Steam: Avatar Legends: The Fighting Game (appid 2424420) e Pro Jank Footy (appid 3621330). Preciso da Steam FECHADA para repor (ela regrava o arquivo ao sair e engoliria a correção). Feche a Steam e eu reponho.
```

Na mesma foto, o chip do topo dizia **«Perfil ativo: Mortal Kombat»**.

**Tudo abaixo foi medido no fonte e no journal. Nada foi medido na tela** — é o
Passo 1 desta sprint, e duas das quatro causas só se fecham lá.

---

## §1 — A FRASE: três pedaços colados, e nenhum é notícia do gesto

| pedaço | quem escreve | o defeito |
| --- | --- | --- |
| «Perfil ativado: Future Knight» | `profiles_actions.mensagem_de_ativacao` | nenhum — é o que o gesto fez |
| «— Aplicado, menos: luzes, gatilhos, button_actions.» | `profiles_actions.relato_da_ativacao` + `footer_actions._mensagem_de_aplicacao` | põe em «não entrou» TODA seção cujo estado não é `"aplicado"` |
| «· 2 jogos nunca receberam…» | `a10_perfis._com_a_carona` colando `carona_do_wrapper.passada` | notícia da Steam grudada na frase de um perfil |

### 1.1 «button_actions» não falhou — e chega cru

`src/hefesto_dualsense4unix/profiles/manager.py` grava
`relatorio["button_actions"] = "de_fabrica"` quando o perfil não opina sobre os
botões. **Isso não é falha: é o perfil usando os botões de fábrica.** O
`relato_da_ativacao` não distingue, e a chave não tem nome de tela em nenhum dos
dois dicionários (`_NOMES_DAS_SECOES_DA_ATIVACAO`, `footer_actions._NOMES_DE_SECAO`)
— então sai `button_actions`, em inglês, no meio da frase.

### 1.2 «luzes, gatilhos» — o estado exato não está no journal

O `profile_activated` das 01:22:39 não registra as seções. Os estados que não
são `"aplicado"` incluem `adiado_lock_manual` (`daemon/lifecycle.py`: o gesto
manual dela vence o perfil por 30 s) e os `ignorado_*`. **O Passo 1 lê o corpo
do `profile.switch`** e decide o caminho:

* se o daemon **reaplica** a seção quando a trava vence — a tira não tem o que
  dizer, e calar é a verdade;
* se ele **descarta** — o defeito é de produto, e a cura é o mecanismo que
  reaplica, não uma frase que descreve a perda (princípio dela de 05/09: *a
  máscara não custa feature*, e a mesma régua vale aqui).

### 1.3 A Steam na tira dos perfis

Para jogo que **nunca recebeu** as opções não existe metade curta
(`sentinela_do_wrapper._frase_do_aviso` só a escreve para regressão), então
`_com_a_carona` cola a frase longa — duas linhas, e a reticência come o fim.

**O que o journal diz do reparo, e ele é só metade:** em 12 e 13/09 o
`hefesto-steam-input-guard` rodou a cada ~30 min e registrou **40
`reparo: reparado`**, todos de REGRESSÃO (o PRAGMATA perdendo a linha). **Nenhuma
linha de jogo que nunca recebeu.** O cartão da Steam na aba Lançadores tem a
notícia inteira (`a07_lancadores._VigiaDaSteam.noticia`).

### A cura

**A tira da aba Perfis diz o que o gesto fez, e só isso.** Decisão de PO,
sustentada pela palavra dela de hoje e pela de 07/09 (*a tela nunca confessa
dívida nossa*):

1. `"de_fabrica"` e os `ignorado_*` que não são falha saem do «não entrou»;
2. seção sem nome de tela nunca chega crua — um nome ou nada;
3. a notícia da Steam sai da tira dos perfis — **e antes disso se confere** que
   o reparo alcança jogo NOVO, não só regressão. Se não alcançar, o defeito é do
   reparo, e ele ganha sprint própria: tirar a frase sem isso esconderia um jogo
   sem controle;
4. o que sobrar de «não entrou» depois do 1.2 vira mecanismo, não texto.

---

## §2 — A LUPA NÃO FILTRA, e a cadeia parece inteira no fonte

`aba10.campo_da_lupa` publica `data-hef-vivo="procurar"` → o piloto manda o
`valor` (`hefesto_vivo.carga_do_alvo`) → `a10_perfis.procurar` guarda
`_PROCURA` → o tique aplica `_filtrada` antes de montar o `blocos`.

**Lendo, nada falta — e é por isso que a causa é do Passo 1.** A regra da casa
para tela não tem exceção: abrir, digitar, medir. O que medir, nesta ordem:

1. o vivo chegou? (`vivos_atendidos` / `vivos_recusados` do piloto);
2. `_PROCURA` mudou?
3. o `<tbody>` foi trocado? (número de `<tr>` antes e depois);
4. o campo foi reescrito por cima do que ela digitou?

---

## §3 — O ↻ EM DOBRO: são dois gestos com o mesmo desenho

| ao lado de | gesto | desenho |
| --- | --- | --- |
| «Perfis salvos» | `recarregar` | `aba10.RECARREGA` |
| «Editar» | `voltar-a-de-ontem` | `aba10.DESFAZ` — **o mesmo traço, espelhado** |

A 11 px ninguém separa os dois. O «Voltar à de ontem» foi para o «Editar» por
ordem dela de 11/09 (as duas falas estão no comentário de `aba10.py`, antes do
botão «Ativar»).

**A cura: `DESFAZ` ganha desenho próprio** — relógio com seta, que é a
convenção de «voltar a uma versão». Decisão de PO; a foto é dela.

---

## §4 — O PERFIL QUE NÃO ACOMPANHA

**O journal diz uma coisa só:** entre 01:13 e 01:26 o daemon registrou UMA
ativação — `profile_activated name='Future Knight' origin=manual`, às 01:22:39.
Nenhuma para Mortal Kombat.

### 4.1 O chip mostrava o desenho, não o produto

As dez páginas publicadas em `src/hefesto_dualsense4unix/interface/paginas/`
nascem com `<span class="pa-nome" data-campo="perfil">Mortal Kombat</span>` — o
exemplo congelado do mockup, conferido página a página. Quem escreve o nome real
é `pacotes.topo()` → `perfil.nome_do_ativo`. **O chip dizer «Mortal Kombat» é a
pintura que não chegou a ele** — por que não chegou, o Passo 1 mede.

A cura mínima que independe da causa: a página nasce com `—`. Pintura que falha
passa a mostrar ausência, nunca um perfil falso. **Esta sprint cura a página
10**; as outras nove são do dono do topo e ficam relatadas na entrega.

### 4.2 O «Ativar» age sobre o último NOME clicado

* `a10_perfis.selecionar` só dispara na célula do NOME
  (`<td data-hef="perfis.linha.nome">`). Clicar em «Prioridade» ou «Funciona em»
  não muda o alvo;
* `_escolhido()` só segue o ativo enquanto `_ESCOLHIDO` está vazio. Depois do
  primeiro clique ele **nunca mais** acompanha o perfil que vale — nem o
  autoswitch, nem uma troca feita em outra aba.

Daí a recusa que ela recebeu: *"“Future Knight” já é o perfil que está
valendo"* — certa sobre o daemon, e errada sobre o que a tela mostrava.

### A cura

1. **a linha inteira seleciona**, não só a célula do nome;
2. **quando o perfil que vale MUDA** (a borda, venha de onde vier), o escolhido
   passa a ser ele — a escolha livre vale até a próxima troca;
3. o chip da página 10 nasce `—` (§4.1).

---

## §5 — A ORDEM

1. **Medir na tela** — piloto `--oculta`, com
   `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` e cópia de
   `~/.config/hefesto-dualsense4unix/profiles/` antes (o piloto roda as
   migrações no disco dela — memória de 05/09). Os quatro itens do §2, o chip do
   §4.1, o corpo do `profile.switch` do §1.2 e o reparo de jogo novo do §1.3;
2. **§4** — o dano maior: o botão age num perfil que ela não está vendo;
3. **§1**;
4. **§2**;
5. **§3**;
6. `--publicar 10`, foto antes e depois, clique, mordida.

## §6 — O QUE MORDE

* **§1:** relato com `button_actions: de_fabrica` → a frase é só «Perfil
  ativado: X». Arrancar a cura → volta o «menos: button_actions»;
* **§1:** nenhuma frase desta tira contém chave de seção crua — a régua lê os
  nomes das DUAS tabelas, nunca uma lista digitada;
* **§2:** digitar parte de um nome → sobra só a linha dele; apagar → voltam
  todas. Medido no DOM do piloto, não em função pura;
* **§3:** o `path` de `DESFAZ` não é o de `RECARREGA` espelhado;
* **§4:** ativo muda de A para B com `_ESCOLHIDO = A` → o tique seguinte
  escolhe B. Clicar na célula «Prioridade» de C → o Ativar mira C;
* **§4.1:** a página 10 publicada não contém nome de perfil no `pa-nome`.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** | não se aplica: a aba fala do perfil da máquina, e nada aqui depende de transporte |
| **por BT** | idem |
| **no perfil** | `_ESCOLHIDO` e `_PROCURA` são memória da janela e **não vão ao disco** — decisão de 11/09 mantida. A frase lê o relatório do daemon; o perfil não ganha campo |
| **por controle** | não se aplica às quatro queixas. A tabela «ajustes por controle» da mesma aba não é tocada |

## O que é dela

**A foto.** O desenho novo do ↻ e a tira calada fecham com o olho dela
(PROVA-DE-TELA-01).
