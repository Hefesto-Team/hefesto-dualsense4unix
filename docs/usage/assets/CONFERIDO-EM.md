# Quando estas imagens foram conferidas pela última vez

Este arquivo existe porque o portão `test_as_fotos_nao_ficam_atras_do_codigo_da_tela`
compara **commits**, não bytes: ele pergunta se o último commit que tocou
`docs/usage/assets` é mais novo que o último que tocou o código da tela.

Isso deixa um estado sem saída: quando o código da tela muda mas **o desenho
não**, `retratar_abas.py` produz imagens idênticas às que já estão versionadas,
o git não tem o que commitar, e o portão fica vermelho para sempre — mesmo com
a conferência feita e o resultado correto.

Não é falso positivo: o portão está certo em exigir a conferência. O que faltava
era um lugar para **registrar que ela aconteceu**. É este arquivo.

## Como usar

Rode `scripts/gui-captura/retratar_abas.py`. Se as imagens mudarem, commite-as —
e a mudança de desenho é palavra dela, não de quem tirou a foto
([PROVA-DE-TELA-01](../../process/sprints/2026-07-27-PROVA-DE-TELA-01-dez-minutos-de-olho-antes-de-qualquer-leva.md)).
Se **não** mudarem, acrescente uma linha aqui embaixo e commite este arquivo: o
portão volta ao verde e fica escrito quem conferiu, quando, e contra qual commit.

## O registro

| data | commit do código conferido | resultado |
|---|---|---|
| 15/08/2026 | `9441678` — a numeração dos jogadores | **10 abas, todas idênticas.** O commit mexeu na fonte do número do jogador (`coop.py`, `ipc_handlers.py`), que é dado e não desenho: nenhum pixel mudou. Conferido rodando `retratar_abas.py` e comparando com `git status docs/usage/assets/` — zero arquivos diferentes. |
| 18/08/2026 | `afe9ba7` — o rodapé que saía pela borda, mais a leva do microfone no perfil e a guarda do foco errante | **10 abas, todas idênticas.** O commit de ontem mexeu no orçamento de altura do rodapé (`controller_card.py`, `main.glade`) e a leva de hoje acrescentou o escritor do microfone no rascunho (`controller_card.py`, `draft_config.py`) — dado e fiação, não desenho. Conferido rodando `retratar_abas.py`: `git status docs/usage/assets/` voltou vazio, zero arquivos diferentes. |
| 22/08/2026 | `85540ed` — a costura da aba Configurações | **11 abas, e o registro passa a ter doze arquivos.** A aba nova entrou em `c6b8daa` e as dez existentes foram refotografadas junto, mudando só pelo deslocamento da tira; nenhuma delas mudou de novo até aqui. A `readme_configuracoes.png` mudou em quatro commits da leva (`c6b8daa`, `d74bd3e`, `7a52931`, `85540ed`), acompanhando as seções que iam ficando prontas. |
| 22/08/2026 | a coluna "O que é" da seção "A mesa" | **Só a `readme_configuracoes_inteira.png` mudou** — as dez abas antigas e a foto acima da dobra ficaram idênticas, porque a coluna nova nasce abaixo dos 1080px. A aba passou a pedir 1993px de altura (eram 1921): +72px, e não os +384px da primeira tentativa, que usava grade de três colunas fixas. Conferido rodando `retratar_abas.py` e comparando `git status docs/usage/assets/`: um arquivo diferente, o esperado. |
| 22/08/2026 | a lista do Steam Input no editor de perfil | **Só a `readme_perfis.png` mudou.** E ela mudou por duas razões: a lista nova, e o fato de a caixinha do Steam Input **nunca ter sido fotografada** — ela só aparece com "Aplica a = Jogo da Steam", e os três perfis da foto casavam por `process_name`. O retrato passou a escolher "Jogo da Steam" e a injetar três appids inventados. De quebra, o script deixou de rodar o `_instalar_lista_de_jogos_do_pc`, que varria a biblioteca Steam DELA para montar a completação — leitura de disco dela num script de foto. |
| 22/08/2026 | `2a614c3` — a VAO-01, e a foto que montava a aba diferente do produto | **Só a `readme_gatilhos.png` mudou**, e ela mudou por DOIS motivos: a moldura da seção parou de esticar (`vexpand=False` mais `valign=start`, porque o pai é um Box horizontal e o `expand` do packing só distribui largura) e o retrato passou a montar os 19 modos pelo método de PRODUÇÃO. A montagem à mão pedia 1016px; o produto pede 482px. A foto ganhou a linha *"Sem resistência."*, que nunca tinha aparecido na documentação. |
| 22/08/2026 | `49797f8` — a central ganha tela | **As duas fotos da Configurações mudaram**, e é o caso que a nota abaixo descreve: a de 1920x1080 e a esticada. Entraram a coluna "O que é" nascendo LIDA do kernel (com `Corrigir` ao lado) e o campo de nome por adaptador. A bancada de mentira do retrato ganhou um aparelho que o kernel classifica e um que ele não classifica — sem os dois, a documentação mostraria só o caminho feliz. |
| 23/08/2026 | `3de95ff` — cinco abas paravam de fotografar o glade cru | **Sete PNGs mudaram** (Configurações, Configurações inteira, Emulação, Lightbar, Navegação, Rumble, Sistema) — a P10 (§ da própria sprint) deu host de produção às cinco que ainda saíam do XML cru. Este registro faltava: o ensaio rodou (`PROVA-DA-FOTO.txt` traz `ensaio: 2026-08-23 21:12`) e ninguém escreveu a linha aqui, o que a Z0-01 (24/08/2026, §2.2/M8) mediu como fato caduco na §"conferidas pela última vez em 22/08/2026" do `interface.md`. |

## A décima primeira quebra a regra de um PNG por aba

A **Configurações** é a única que pede mais altura do que a janela tem, e desde
22/08/2026 o `retratar_abas.py` grava **duas** imagens dela: a de 1920x1080, que
é o que se vê, e a `readme_configuracoes_inteira.png`, esticada até a altura que
a página pede. A lista de abas esticadas é `ABAS_ESTICADAS`, no próprio script.

Quem conferir e vir só a primeira mudar não está diante de um erro: a segunda só
muda quando muda o que está **abaixo** da dobra. As duas nascem da mesma
execução, e commitar uma sem a outra deixa a documentação mostrando duas versões
da mesma tela.
