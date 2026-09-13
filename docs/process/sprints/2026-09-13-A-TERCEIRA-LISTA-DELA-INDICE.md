---
sprint: A-TERCEIRA-LISTA-DELA-INDICE
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  A-TERCEIRA-LISTA-DELA-INDICE:
    - docs/process/sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md
bancada: false
depois_de: []
---

# A TERCEIRA LISTA DELA — o índice da leva de 13/09/2026

**13/09/2026, madrugada.** Ela abriu o produto, ainda na versão de antes da
leva das frases, e mandou numa mensagem só:

> *"2 jogos nunca receberam as Opções de Inicialização do Hefesto na Steam: Avatar Legends: The Fighting Game (appid 2424420) e Pro Jank Footy (appid 3621330). Preciso da Steam FECHADA para repor (ela regrava o arquivo ao sair e engoliria a correção). Feche a Steam e eu reponho. esse tipo de info segue aparecendo nas abas"*
>
> *"esse tipo tambem tem que parar de aparecer"* — com a foto da aba Gatilhos e a caixa laranja *«Esse número é maior do que a quantidade de controles ligados»* <!-- noqa-acento: citação literal dela -->
>
> *"reconectar c ontroles segue dando pau,. falo do posicionamento e formato dele. ele segue sambando."* <!-- noqa-acento: citação literal dela -->
>
> *"o sack boy, não sei se tem outros na mesma condição, talvez o pragmata ou madjack. mas o sackboy não tá respeitando o modo e a máscara setado na aba jogar. ele tá diferente do resto dos jkogos. preciso que faça eles funcionarem como os demais nenhum jogo tem que ter esse tipo de exclusividade em termos de config fora da interface. outra coisa não sei se nossos botões da aba sistema fazem o que deveriam fazer de fato e se funcionam"* <!-- noqa-acento: citação literal dela -->
>
> *"outra coisa se ler sobre como descobrimos como funcionava o a escrita do lightbar dentro da steam e como fizemos os guards funcionarem lá pra isso sempre se autoaplicar. tenho receio que nossas features não cheguem aos jogos pelo mesmo motivo ou semelhantes. inclusive acho que o lightbar perdeu essas qualidades que tinhamos, ou foi desligado recentemente. Preciso que a auditoria revele isso."* <!-- noqa-acento: citação literal dela -->
>
> *"não vamos adicionar botões novos no layout no máximos vamos tirar e nxugar ou mexer o minimo. nada de adicionar. temos que fazer a interface funcionar porinteiro. além disso mande agentes executarem as demais sprints a serem concluidas no repo. faça com calma e zelo. todas as decisoes ja foram tomadas no passado não precisa de mim pra nada. sempre documente pra evitar que uma queda nos derrube"* <!-- noqa-acento: citação literal dela -->

## §0 — O processo desta leva (ordem dela)

1. **A sprint nasce aqui, commitada, ANTES de qualquer agente.**
2. **No máximo três agentes por sprint, em série:** ESTUDO (só lê e mede,
   devolve o achado e a posse real), IMPLEMENTA (na árvore própria da sprint),
   VALIDA/CORRIGE (foto, clique, mordida, portões; corrige o que achar).
3. **Quem coordena** escreve o estudo na sprint, acerta a posse, despacha,
   costura na integração, roda portões e suíte, leva ao `dev`, empurra e
   instala. O install final usa o sudo que ela autorizou — a senha não vai para
   arquivo nenhum.
4. **Nada de botão novo.** Tirar e enxugar pode; mexer o mínimo.
5. **Decisão:** as decisões já estão registradas na casa; quem decide escreve a
   razão e o endereço da decisão antiga que a sustenta.
6. **As páginas geradas não são posse de ninguém nesta leva.** Toda sprint que
   muda gerador, pacote cravado ou `topo.html` regera e publica NA PRÓPRIA
   árvore, para medir e fotografar; na costura, quem coordena regera as dez sobre
   o código costurado e publica. HTML gerado nunca se mescla à mão.

## §1 — O que o estudo respondeu, em uma linha cada

* **A caixa laranja** é a recusa do número acima dos controles ligados, e ainda
  pousa na aba Iluminação; o canal inteiro de recado sai da tela.
* **O «Reconectar»** não anda mais para os lados; ainda pula 62 px para cima
  quando um tique do serviço não responde, e 27 px com zero controles.
* **O Sackboy** tem duas exclusividades fora da interface: o install script que a
  casa contava como jogo vivo, e o Steam Input que a própria Steam liga por jogo —
  o Pragmata e o Mullet Mad Jack têm a segunda.
* **A aba Sistema:** seis botões funcionam, cinco funcionam em parte, o do Proton
  não funciona com a Steam aberta, e o «Ver os plugins» não tem como funcionar e
  sai.
* **A luz não foi desligada** e nenhuma guarda caiu; o que ela reafirma no jogo é
  a cor fosca que o cliente Steam deixou no vpad. E o giroscópio não chega ao jogo
  em Modo Virtual — é o laudo da SENSORES-NO-JOGO-01, que vira sprint de produto.
* **Um portão estava vermelho no `dev` empurrado** (`citacoes-no-codigo`): curado
  na costura desta leva.

## §2 — As sprints e a ordem

| sprint | o pedido | onda |
| --- | --- | --- |
| costura: ALTURA-DA-VISTA-01 · SENSORES-NO-JOGO-01 · TOUCHPAD-NO-3DS-01 | as três entregas que a triagem liberou; a ALTURA primeiro, porque o `topo.html` entra nas dez páginas | quem coordena, antes da onda 1 |
| [FRASES-E-DICAS-01](2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md) | a caixa laranja e a frase da Steam: o recado sai da tela; o número fora diz só «Player N» | 1 |
| [FRASES-E-DICAS-02](2026-09-13-FRASES-E-DICAS-02-as-dicas-e-as-linhas-que-avisam-viram-estado.md) | as dicas e as linhas que avisam nas abas 02, 03, 07 e 08 viram estado | 1 |
| [JOGO-SEM-EXCLUSIVIDADE-01](2026-09-13-JOGO-SEM-EXCLUSIVIDADE-01-nenhum-jogo-foge-do-modo-e-da-mascara-da-aba-jogar.md) | o install script que fingia jogo vivo; o Steam Input por jogo fora da lista | 1 |
| [LIGHTBAR-NA-STEAM-01](2026-09-13-LIGHTBAR-NA-STEAM-01-a-luz-dentro-da-steam-e-as-guardas-que-se-autoaplicavam.md) | a cor retida do cliente Steam deixa de virar camada do jogo; a telemetria diz o valor | 1 |
| [F1-REMAPEAR](2026-09-11-F1-REMAPEAR-as-vinte-e-duas-linhas-e-o-motor-que-nao-existe.md) | o motor do remapeamento que a aba 06 já desenha | 1 |
| [VAO-DO-ESQUELETO-01](2026-09-11-VAO-DO-ESQUELETO-01-a-faixa-vazia-de-tres-paginas-e-a-decisao-de-27-08.md) | o salto de 2 px da fita e o «Mortal Kombat» do chip (absorve o §4.1 da PERFIS-TIRA) | 1 |
| SENSORES-NO-JOGO-02 | o giroscópio que não chega ao jogo em Modo Virtual | 1: só o estudo |
| [SISTEMA-BOTOES-01](2026-09-13-SISTEMA-BOTOES-01-cada-botao-da-aba-sistema-faz-o-que-diz.md) | cada botão da aba Sistema (absorve as §3 e §4 da TELA-CALADA-04) | 2, depois da FRASES-01 |
| [RECONECTAR-SAMBA-02](2026-09-13-RECONECTAR-SAMBA-02-o-botao-que-ainda-muda-de-lugar-na-janela-dela.md) | o pulo vertical: o tique mudo, os chips e a frase da mesa vazia | 2, depois da FRASES-01 |
| [MIC-SEM-FONTE-01](2026-09-09-MIC-SEM-FONTE-01-a-razao-chega-depois-do-arrasto-e-a-tarja-cobre-a-linha-de-cima.md) | o microfone cinza antes do arrasto | 2, depois das duas FRASES |
| [DICA-DA-COR-01](2026-09-09-DICA-DA-COR-01-o-aviso-sai-da-janelinha-do-gtk-e-o-x-ganha-pixel.md) | só o X do tom tomado | 2, depois da FRASES-01 |
| TELA-CALADA-04 · PERFIS-TIRA-BUSCA-ATIVO-01 | — | absorvidas |
| FONE-01 | — | caducou: pediria deslizante novo |
| MESA-DE-QUATRO-01 · LUZ-NO-RADIO-01 · OS-GESTOS-QUE-SO-ELA-PODE-FAZER | as provas de aparelho de toda a leva | bancada, com ela |

## §3 — Onde está o estado, para sobreviver a uma queda

* **A integração:** `/mnt/Apate/Desenvolvimento/hefesto-voo/_integra-1309`, branch
  `onda/1309`. O `dev` dela recebe por fast-forward.
* **Os lotes:** `/mnt/Apate/Desenvolvimento/hefesto-voo/_lotes/<lote>/args.json`
  e as árvores em `/mnt/Apate/Desenvolvimento/hefesto-voo/hefesto-voo/<SPRINT>-opus`.
* **Os estudos inteiros e as duas triagens**, fora do git:
  `/mnt/Apate/Desenvolvimento/hefesto-voo/_lotes/1309-terceira/`.
* **O que cada agente entregou:** `docs/process/agentes/2026-09-13/<SPRINT>-*.md`
  na branch `voo/<SPRINT>-opus`. Conferir com `git cherry onda/1309 voo/<SPRINT>-opus`.
* **O ONDE PARAMOS do dia:**
  `docs/process/2026-09-13-ONDE-PARAMOS-a-tela-que-parou-de-narrar-e-os-quatro-microfones-no-ar.md`.
* Esta tabela é atualizada a cada onda, no mesmo commit que muda o estado.
