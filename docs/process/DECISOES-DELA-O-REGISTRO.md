# As decisões dela — o registro

**Aberto em 05/09/2026**, depois de ela dizer:

> *"pior é que essas dúvidas e decisões já foram tomadas e repetidas várias
> vezes. acho que tem algo no projeto desatualizado."*

Uma linha por decisão **dela**. Da mais recente para a mais antiga. O laudo que
mediu a queixa está em
[`2026-09-05-POR-QUE-A-FILA-REPETE`](2026-09-05-POR-QUE-A-FILA-REPETE-a-queixa-dela-medida.md).

---

## O QUE FALTA NESTE REGISTRO, e por quê

**Este arquivo está INCOMPLETO, e é melhor dizê-lo do que fingir o contrário.**

| o que está aqui | o que não está |
| --- | --- |
| as decisões dela de **22/08 a 05/09** que consegui recuperar lendo `docs/data/decisoes-dela.csv`, os documentos `AS-N-DECISOES-DELA-*`, `mockup/TODO-DELA.md` e as mensagens de commit | tudo o que ela decidiu **antes de 22/08** — o repositório tem decisões dela desde 27/07 (`PROVA-DE-TELA-01`) e nenhuma varredura foi feita nesse período |
| o verbatim, quando o arquivo de origem o guardou | o verbatim de **62 das 108** linhas de agosto do registro em CSV, que trazem a decisão mas não a frase dela |
| a prova, sempre com `arquivo:linha` ou `commit` | uma varredura exaustiva: as marcas de decisão dela aparecem em **570 arquivos `.md`** de `docs/` (de 991) e em mais **468** fora de `docs/`. Este arquivo leu as fontes concentradas, não os 1.038 |

**Por que ficou incompleto:** o levantamento foi feito em uma sessão, em modo
somente-leitura, a partir das fontes que se declaram registro. Completá-lo é
trabalho de varredura, e o portão `fila-dela` proposto no §6 do laudo é o que
faz esse trabalho aparecer como vermelho em vez de como esquecimento.

**Regra deste arquivo:** só entra o que **ela** decidiu. Decisão tomada em nome
dela por delegação **não entra aqui** — ela tem o seu bloco no fim, separado de
propósito, porque foi a mistura das duas que produziu a repetição de hoje.

---

## 13/09/2026

Ela apontou que o modo da aba Jogar diz «aplicado» e não muda, e que o texto do
«Xbox» é o da máscara. Com o estudo já em voo, deu a regra.

| data | o que ela decidiu | verbatim | prova |
| --- | --- | --- | --- |
| 13/09 | **O MODO é a base, e o PS + R3 é o mesmo modo que o chip.** A MÁSCARA vem por cima, independente do modo: é como o jogo vê a entrada. Os dois valem com o jogo aberto, e o que o PS + R3 escolhe fica gravado no perfil | *"o modo é base (ele o ps + r3) aí ap´os o modo de conexão, independente do escolhido anteriormente temos a máscara que é como o jogo se apresenta em termos de inputs apesar do modo de conexão escolhido."* · *"eles precisam funcionar durante o jogo tá bom?"* · *"inclusive o ps +r3 e isso fica setado no perfil"* <!-- noqa-acento: citação literal dela --> | [MODO-DE-CONEXAO-01](sprints/2026-09-13-MODO-DE-CONEXAO-01-o-degrau-xbox-que-diz-aplicado-e-nao-vale-e-o-texto-que-e-da-mascara.md), onde a regra e a cura moram |

---

## 08/09/2026

Ela abriu o produto INSTALADO, com os quatro DualSense na mesa (P1/P2 no cabo,
P3/P4 no rádio), fotografou a tela e apontou quatro coisas.

| data | o que ela decidiu | verbatim | prova |
| --- | --- | --- | --- |
| 08/09 | **O desenho ESTICA com a janela, com teto.** Ela viu a sobra da cor da casa em volta do desenho na janela maximizada; a recomendação foi levada a ela com as razões e ela aprovou | *"o background fica completamente preto"* · e sobre a recomendação: *"eu confio em vc, manda ver"* | `interface/topo.html`, `.janela{width:min(100%,1600px)}`; o teto é hipótese medida nas dez abas em quatro larguras — a coluna por jogador da Gatilhos ganha 46% (228 -> 333px) e a linha de leitura dobra em vez de triplicar. Régua: `tests/unit/test_a_janela_estica_com_teto.py` |
| 08/09 | **A barra de título não fala a língua de dentro.** O subtítulo dizia *"as dez abas, vivas"* — o nome que ESTA CASA deu ao piloto | *"Temos o Termo as dez abas vivas no title da janela"* | saiu de `interface/hefesto_vivo.py`; a moldura fica só com "Hefesto". Portão novo: `scripts/check_a_janela_nao_confessa.py`, que na primeira corrida achou a SEGUNDA ocorrência — a mesma frase na dica do `.desktop`, que a dock mostra antes de a janela existir |
| 08/09 | **Nas abas em que a fita não escolhe, o chip marcado fica cinza como os outros** | *"o player 1 tipo no caso cosmic red - cabo, fica sempre selecionado com borda diferente mesmo nas abas que cada player tem sua propria config. conseguimos deixar ele cinza como os demais?"* <!-- noqa-acento: citação literal dela --> | `interface/topo.html`, `.fita.inerte .chip.on`; vale para as sete abas de fita inerte. Régua: `tests/unit/test_a_fita_inerte_nao_acende_ninguem.py`, que mede a cor COMPUTADA na página publicada |
| 08/09 | **O "Não trocar de perfil sozinho" vai para o canto superior direito do bloco Modo**, na linha do título, com a gramática do "Banco de provas" da Navegação. Embaixo dos modos ele lia como um quinto modo | *"esse não trocar de perfil. Pode colocar ele no canto superior direito do bloco tipo esse banco de provas na guia navegação."* | `interface/aba01.py`; o gesto não mudou. Régua: `tests/unit/test_o_cadeado_mora_no_canto_do_bloco.py`, que mede a geometria E prova que `data-gesto`, `data-campo` e o rótulo continuam os mesmos |

**E uma decisão de 26/08 caducou de vez.** *"A caixa 'Não trocar de perfil
sozinho' SAI — o perfil ativo já diz isso"* foi desfeita por delegação em 04/09
(decisão [03] do PO) e a caixa está viva desde então. Em 08/09 ela pediu para
MOVÊ-LA, o que confirma a caixa. **A legenda das duas páginas
(`interface/aba01.py` e `interface/fim.html`) ainda dizia que a caixa "saiu"** —
descrevia uma remoção desfeita havia quatro dias. Foi a legenda que estava
velha, e é ela que foi corrigida.

---

## 05/09/2026

| data | o que ela decidiu | verbatim | prova |
| --- | --- | --- | --- |
| 05/09 | **A máscara não custa feature — nunca.** Recusou a categoria inteira de "aviso de limitação": onde a máscara tira algo, o produto cria mecanismo em vez de descrever a perda | *"Pode medir, mas a ideia é que o de falhas e limitações. Criamos mecanismos pra usarmos todas as feature. Exemplo controle do Xbox não tem microfone mas se o Mic do dualsense passa a ser lido a parte via Mic virtual. Usaríamos essa feature do controle mesmo no Xbox. Mesmo problema BT. Hj já funciona assim, sem a parte do Mic virtual."* <!-- noqa-acento: citação literal dela --> | `docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md:12-18` |
| 05/09 | **A palavra "mesa" sai da interface inteira** — no sentido "conjunto de controles". No sentido "escrivaninha" fica | *"não é pra ter mesa em nada da interface"* | commit `80b8c730`; 26 ocorrências trocadas, 13 mantidas na aba 08 |
| 05/09 | **O "Auto" e a linha de mesa saem da aba Vibração.** Três modos sempre; a economia de bateria tem um dono só, na aba Sistema | *"não é pra ter mesa em nada da interface. (…) segue os três modos sempre. clicou em perfil de energia econômico na aba sistema todos vão pra vibração manual. o resto é desnecessário e só polui e deixa difícil entender"* | commit `38cdde70`; citada em `src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:90-98` |
| 05/09 | **A faixa "Estado" sai da aba Vibração** | *"pq temos uma linha de estado se o estado em vibração sempre vai ser o jogo mandando os input pro controle e a gnt aumentando eles ou diminuindo? remove ela não faz sentido"* | commit `dcaaa051`; `docs/process/sprints/2026-09-05-ONDA-QUATRO-INDICE.md:85` |
| 05/09 | **O botão da sobreposição Vulkan diz "Vulkan" com todas as letras.** O verbo "corrigir" NÃO entrou, e a razão é medida: o clique só olha | *"o procurar sobreposição de novo deveria ser Corrigir Sobreposição do Vulkan, não?"* | commit `8ac42e98`; ficou "Tirar a sobreposição Vulkan" |
| 05/09 | **A aba com um controle só mostra só aquele controle** | *"temos que entender se só tem um controle conectado só aparece config daquele. aba cinco tá errada."* | commits `390302ea` (aba 05) e `d0ea7b50` (as dez) |
| 05/09 | **O "Todos" da fita some quando há um controle só** | *"só faz sentido aparecer o todos se tiver mais de um controle conectado"* | commit `ee71f868` |
| 05/09 | **O perfil padrão chama-se "Personalizado", não `meu_perfil`** | *"Meu_perfil como perfil default não deveria existir … acho Personalizado melhor"* | commit `cb41c851`, com migração que preserva o disco dela |
| 05/09 | **"mesa" vira "objeto" e sinônimos onde o sentido é físico** | *"muda o termo pra objeto e sinônimos nesses casos"* | commit `61eb1fb6`, 24 arquivos |
| 05/09 | **As ondas sonoras do alto-falante e do microfone têm de ser reais** | *"ondas sonoras do auto falante e do microfone devem ser reais"* | commit `ba70c4b3`; `integrations/ondas_de_som.py`, novo |
| 05/09 | **Um deslizante para a velocidade do cursor e outro para a rolagem** | *"velocidade do cursor e da rolagem coloca um slicer pra cada"* | commit `ba70c4b3` |
| 05/09 | **A aba 10 não pode ter a banda morta no título** | *"a aba dez tem um espaço vertical bizarro desnecessário no título"* | commit `ba70c4b3`; 37 px reservados passam a colapsar |
| 05/09 | **A aba Emulação não devia ter voltado** — e não voltou ao produto; voltou às FOTOS da documentação | *"pq a aba emulação voltou? Não era pra ela ter voltado"* | commit `62541ec8`; nasceram `docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md` e `docs/usage/A-JANELA-ANTIGA-o-que-mudou-de-lugar.md` |
| 05/09 | **O perfil se lembra da configuração de cada aba para cada controle** | *"o perfil vai se lembrando de cada config de cada aba pra cada controle"* | `docs/process/2026-09-05-ONDE-PARAMOS-as-treze-queixas-e-os-instrumentos-que-mentiam.md:35`; fases 0 e 1 fechadas |
| 05/09 | **Mandar agentes em loop para os outros casos** | *"manda em loop agentes pra esses outros casos também"* | mesma tabela, `:34`; três ondas, doze frentes |
| 05/09 | **A aba 10 continuava com o problema anterior** — a coluna "Ajuste próprio" escondia a sexta seção | *"aba 10 tá com o mesmo problema de antes. nada mudou"* | mesma tabela, `:17`; commit `ba70c4b3` |
| 05/09 | **O botão de correção do Vulkan tem de existir na tela nova como no GTK** | *"e o botão de correção do vulkan? veja no gtk"* | mesma tabela, `:18` |

---

## 04/09/2026 — as dezesseis da madrugada

Fonte única: `docs/process/2026-09-04-AS-DEZESSEIS-DECISOES-DELA-e-as-sprints-que-nascem.md`.
**Nenhuma das dezesseis tem linha em `docs/data/decisoes-dela.csv`** — conferido
por id, e é o buraco que a §4.3 do laudo mede.

| id | o que ela decidiu | verbatim | prova |
| --- | --- | --- | --- |
| D-01 | O recado de SUCESSO mora no próprio cartão. **Fecha cinco abas com uma peça: 02, 03, 05, 06 e 09** | *"No próprio cartão, como a recusa."* | `:29`; construída em `interface/hefesto_vivo.py:2218` |
| D-02 | A ressalva é linha fixa, e só quando existe | *"Linha fixa só quando HÁ ressalva."* | `:42` |
| D-03 | O botão que vai recusar fica cinza ANTES do clique | *"Cinza antes, com a razão na dica."* | `:55`; peça em `interface/monta.py:1317-1319` |
| D-04 | "Player N" fica | *"Player N, como está hoje."* | `:66` |
| D-05 | "cabo" e "rádio", pela função que já tem dono | *"cabo / rádio, pela função que já existe."* | `:77` |
| D-06 | Casco na borda externa, barra de luz na borda interna. **Ela deu fora das minhas três opções** | *"Casco borda externa lightbar borda interna."* | `:88-89` |
| D-07 | A mesa vazia ganha uma frase, com `+N` no quinto | *"Uma frase por cima dos lugares apagados."* | `:100` e `:104` |
| D-08 | Deslizante de volume nos dois | *"Deslizante nos dois."* | `:112` |
| D-09 | A coluna Atenção cresce até três linhas, com `+N` se passar | *"Até três linhas, o mais grave em cima."* | `:124` e `:126` |
| D-10 | As três frases órfãs da aba Jogar entram na coluna Atenção | *"Todas na coluna Atenção."* | `:151` |
| D-11 | O efeito pronto continua aplicando na hora e trocando o modo | *"Aplica na hora e troca o modo, como hoje."* | `:161`; o documento já dizia *"Nenhuma sprint nasce daqui"* |
| D-12 | O botão do microfone liga o microfone **E** o canal dele — um ato só. **Ela recusou os três arranjos que eu ofereci e corrigiu o conceito** | *"tá errado o conceito da coisa. o botão é pra ligar o microfone e ele ser ouvido no canal específico dele."* | `:167-180` |
| D-13 | O "Cores automáticas" ganha interruptor no topo da Iluminação | *"Um interruptor no topo da aba Iluminação."* | `:223` |
| D-14 | Uma linha de estado da vibração por coluna. **REVOGADA POR ELA em 05/09** (*"remove ela não faz sentido"*) | *"Uma linha de estado por coluna."* | `:251`; revogação no commit `dcaaa051` |
| D-15 | As três regiões do touchpad ficam. **A premissa da minha pergunta caiu inteira** | *"Pedi pra tirar o texto não o touch mostrando os toques."* | `:255-272` |
| D-16 | O Check-up ganha uma linha de veredito | *"Uma linha de veredito no topo."* | `:280` |

---

## 03/09 · 02/09 · 01/09

| data | o que ela decidiu | verbatim | prova |
| --- | --- | --- | --- |
| 01/09 | **Clicar já aplica.** O clique na cor grava e aplica na hora — esta interface não tem rascunho | *"clicar na cor já deveria aplicar a cor no controle"* | `docs/process/2026-09-03-A-LISTA-DELA-o-que-espera-a-palavra-dela.md:55`; citada em `interface/pacotes/a04_iluminacao.py:2035` e `:2347` |
| 02/09 | **A frase da prioridade dos perfis é a dela** | *"Quando dois perfis servem ao mesmo tempo, o de número maior entra."* — e a queixa que a produziu: *"esse texto em perfis nem faz sentido mais"* | `docs/process/sprints/2026-09-02-ROTA-G-a-aba-perfis-e-o-perfil-por-controle.md:173-181` |
| 03/09 | **O trilho de brilho grava na hora, como a cor** | (aplicação da decisão dela de 01/09) | `docs/process/2026-09-03-AS-DOZE-DECISOES-DELA-e-as-quinze-receitas.md:14` |

**Lacuna declarada:** o documento `2026-09-03-AS-DOZE-DECISOES-DELA-e-as-quinze-receitas.md`
anuncia doze decisões dela no título; li o arquivo e só a linha 14 traz uma
atribuída a ela com a frase. **Não achei as outras onze em forma citável** — ou
elas estão no corpo sem a marca de decisão dela, ou o título conta doze
receitas e não doze falas. Fica como dívida de leitura, não como afirmação.

---

## 31/08 e 30/08 — as duas que a fila de hoje atropelou

| data | o que ela decidiu | verbatim | prova |
| --- | --- | --- | --- |
| 31/08 | **Nenhum tooltip nega feature por causa do modo.** O aviso do Modo Nativo e o "custo" do chip Xbox saem da tela | *"independente do modo, todas as features vão funcionar. Então o tooltip falando o contrário é sem nexo."* · *"todos os tooltips tem que ser corrigidos e simplificados."* | `mockup/TODO-DELA.md:129-131`; a ordem também registrada em `docs/data/paridade-gtk-html.csv:9`. **A proibição virou código:** `interface/frases_que_ela_baniu.py:38` |
| 31/08 | **O Modo Nativo já existe no interruptor; qualquer coisa além disso está incorreta** | *"o modo nativo já existe ali (…) e se eu quiser desligar modo hefesto clico em desligado e o modo nativo fica online. Qualquer coisa fora isso tá incorreta."* | citada em `interface/aba01.py:149-151`. **Esta decisão NÃO TEM LINHA no `decisoes-dela.csv`** — foi por isso que a pergunta voltou em 04/09 e de novo em 05/09 |
| 31/08 | **Concluir o mockup primeiro; o layout final vem depois** | *"primeiro nunca terminamos o mockup, por isso não era pra ser feito no layout final. Vamos concluir lá e depois seguimos pra interface."* | `CLAUDE.md`, seção "A LISTA DELA ESTÁ ABERTA"; `mockup/LEIA-PRIMEIRO.md` |
| 31/08 | **A pasta `novo-layout/` se aposenta** | *"o problema original foi não ter separado a pasta do mockup e ter feito a interface usando o HTML do mockup. Se alteramos no layout final a referência do mockup se perde."* | `CLAUDE.md`, mesma seção |
| 30/08 | **Texto na interface é zero.** O que é de média importância vira dica de rato | *"texto na interface é zero, só deixamos se for algo extremamente importante, e se for de média importância vira tooltip"* | citada em `interface/aba06.py:1636-1638` e em `mockup/06-navegacao.html:3452-3454` |
| 30/08 | **O botão do controle sempre manda na interface** — por isso o "Liberar" do microfone não faz sentido ali. Mantida depois de eu medir contra | *"o botão do Controle sempre controla a interface, por isso não faz sentido o liberar ali"* | `docs/data/paridade-gtk-html.csv:76`; manutenção registrada em `docs/process/2026-08-31-ONDE-PARAMOS-o-app-de-dev-anda-sozinho-e-as-reguas-que-calaram.md:142` |

---

## 29/08/2026 — 25 decisões

Todas com linha própria em `docs/data/decisoes-dela.csv`. A coluna "prova"
traz a linha do CSV.

| o que ela decidiu | verbatim | CSV |
| --- | --- | --- |
| As três regiões do touchpad **voltam**, e a decisão de 09/08 caduca | *"eu mudei de ideia"* | `:113` |
| Dois vpads com máscaras diferentes no mesmo jogo **já funcionou** — e ela vai remedir para o registro existir | *"Cara já fizemos isso antes, estranho não ter sido registrado, mas meço novamente e deu certo antes."* | `:104` |
| O acelerômetro **volta à tela e passa a funcionar** | *"não era pra ele sair. era pra ele funcionar."* | `:124` |
| A régua do produto é **qualquer usuário**, não a mesa dela | *"lembrando eu fiz o mapa de todos os controles, não pensando em mim, mas pensando em outros users, afinal o app vai ser GPL3 e gratuito e pensado em acessibilidade pra outros users com autismo ou não."* | `:121` |
| **Tudo que funciona no cabo é possível no rádio** — o PS5 é a prova | *"no ps5 todas as features que usamos aqui funcionam nativamente e nos 4 controles ao mesmo tempo, tudo via bt. No nosso, agora temos tecnologia física de sobra pra fazermos o mesmo."* | `:122` |
| A troca de player à mão oferece só os números que existem agora | *"se tem 3 controles posso escolher só entre os 3 qual é o meu player. Sempre se adaptando nesse sentido."* | `:125` |
| O botão "Ouvir no controle" **sai de vez** | *"inclusive tirar o famigerado ouvir no controle"* | `:100` |
| A interface nova é o mockup HTML num WebView dentro da janela GTK3 | *"sem impeditivo então. manda ve em tudo."* | `:119` |
| A corrente do clean-room **sai do disco** | *"corta essa sprint"* | `:118` |
| O modo de gatilho chama-se **"Arco de flecha"**, sem o inglês | *"ARCO DE FLECHA"* | `:116` |
| As duas perguntas da sala ficam dentro do "Mapear Entradas" | *"Ficam na pop-up, e eu corrijo a sprint."* | `:98` |
| Cada controle é lembrado **dentro de cada perfil**, pela identidade — o caso de uso é ela e o irmão, cada um com o seu controle | (verbatim no CSV, longo) | `:120` |
| A ordem das dez abas é a do mockup que ela aprovou | — | `:99` |
| "Detectar o jogo aberto" mora na aba Perfis | — | `:101` |
| O botão de despausar chama-se **Retomar** e mora na aba Sistema | — | `:102` |
| A máscara por controle vale ao clicar em Aplicar, mesmo com jogo aberto | — | `:103` |
| O teto da vibração é **150%**, e a tela diz quando aparou um perfil | — | `:105` |
| O microfone: a máquina dá o padrão, o perfil sobrepõe | — | `:106` |
| A régua de widget conta os visíveis, com grupo de rádios valendo um | — | `:107` |
| A escolha entre as duas réguas do arranjo espera a divergência medida | — | `:108` |
| O aviso do perfil que nunca entra mora no cartão de saúde da Sistema | — | `:109` |
| O chip "Todos" da fita também abre os quatro cartões | — | `:110` |
| O **Modo Steam** entra na aba Navegação e vira sprint | — | `:111` |
| O remapeamento botão a botão entra, como sprint própria | — | `:112` |
| Os cinco modos de gatilho crescem na própria aba, que passa a rolar | — | `:114` |
| A Metralhadora mostra quatro ajustes; os outros dois não vão à tela | — | `:115` |
| Os oito Estilos de Jogo que faltam nascem desenhados | — | `:117` |
| Alto-falante e microfone viram dispositivo virtual do sistema | — | `:123` |

---

## 28/08/2026 — 10 decisões

| o que ela decidiu | verbatim | CSV |
| --- | --- | --- |
| **A aba Gatilhos de quatro colunas está aprovada** | *"a aba gatilhos atual é perfeita."* | `:93` |
| O quadro Gamepad virtual **sai da interface**; o Perfil de Bateria toma o lugar | *"some da interface; o controle já tá certinho hoje. aquilo foi pra outro momento que não faz sentido na interface hoje."* | `:91` |
| O recibo do rodapé **encurta**, no mockup e no produto — não é removido | *"deixa ela encurtada tanto lá quanto no mockup."* | `:95` |
| Calibrar sensores fica onde está e passa a calibrar os quatro controles | *"ontem vc me deu um argumento bom, mas se conseguirmos fazer funcionar poderiamos deixar ele lá e ele mapearia os 4 controles ao mesmo tempo."* | `:92` |
| A regra de desempate de perfis fica, como rede | *"4 fica caso algo erre."* | `:97` |
| "Sem teto" sai da capa do Desempenho e das quatro linhas de controle | *"Vale Sem teto, do global, abaixo"* | `:94` |
| As janelas da mesa chamam-se "Mapear Entradas" e "Mapear Entrada a Entrada" | *"Desenhar a minha mesa"* (o pedido original, que colidiu com a `D-A-PALAVRA-ENTRADA`) | `:90`; a segunda metade só chegou ao produto em 05/09, commit `8781bac3` |
| As nove sprints que aguardavam a palavra dela estão aceitas | *"nenhuma está na §3"* | `:88` |
| A unidade de tempo do rádio chama-se **TURNO** | — | `:89` |
| A fita acende na aba que ajusta algo do controle escolhido | — | `:96` |

---

## 26/08/2026 — 42 decisões, o dia do redesenho

O dia mais denso do registro. As de verbatim recuperado:

| o que ela decidiu | verbatim | CSV |
| --- | --- | --- |
| **A caixa "Não trocar de perfil sozinho" SAI** | *"some — o perfil ativo já diz isso."* | `:81` — **e ela foi trazida de volta por delegação em 04/09 (`:128`) sem lápide. É uma das três colisões da §5 do laudo** |
| **Clicar no modo já aplica**, e o mesmo vale nas demais abas | *"clicando no modo, tipo gatilho metralhadora — cliquei lá ou usei a fita de seleção do meu player, o negócio já aplica... já funciona como aplicar, mesma coisa nas demais abas nesse sentido."* | `:78` |
| **Aplicar aplica e não grava; Salvar Perfil aplica e grava** | *"Aplicar aplica naquele momento pra aquele perfil mas não salva nada. Eu no jogo aberto já noto isso. Aí Salvar Perfil aplica agora E salva."* (citado no laudo da aba 08) · no CSV: *"ambos os botões fazem o mesmo"* | `:63` |
| A Conexões **grava na hora e lembra** mesmo sem Salvar | *"aplicar e salvar, além de gravar na hora e lembrar se não salvar."* | `:87` |
| A calibração de sensores vai funcionar **também no Modo Nativo** — a Steam é a prova de que dá | *"Vamos fazer esse modo funcionar assim também. escreve a spec e olha o csv de specs e marca lá também pra fazermos. Na steam isso existe então é possível o caminho."* | `:49` |
| A fita do topo é o **único** lugar onde se escolhe o alvo | *"a parte da seleção no canto superior que escolho se é em todos ou no controle X. Não temos que duplicar isso em canto algum."* | `:46` |
| A borda tem a cor do plástico em todo lugar que mostra um controle | *"a borda do controle sempre tem a cor do plástico. tipo o controle ao lado do todos é a borda sempre cor do plástico e quando selecionado o interior segue [a cor de seleção] mas a borda grossa é a cor do plástico"* | `:53` |
| O SVG do DualSense divide-se em dois lados, cada um acendendo com o seu motor | *"Cor do plástico. divide o svgs do dualsense em dois lados esquerdo e direito. Parte esquerda vibra mostrando a cor do motor esquerdo."* | `:57` |
| O caderno de ensaios **não entra** na interface — ela é produto final | *"Na real. Vamos tirar isso da interface. Temos que pensar nela como produto final. Isso é legal pra specs ou html standalone."* | `:75` |
| A aba "No jogo" **funde com a Status** | *"Nossa, esqueci por completo dessa aba aí. Acho que é melhor fundir com status ficando acima da área do controle e isso por controle"* | `:60` |
| A aba **Emulação deixa de existir** | *"ainda faz sentido a guia emulação existir?"* | `:59` |
| O mudo do microfone manda na luz vermelha do plástico | *"O botão deveria mandar nesse caso. Acho que é se tá ativado ele fica aceso, apagado ele tá desligado, e mantém a sua ideia do ícone do slicer."* | `:62` |
| O ambiente "Navegador" **sai** do seletor | *"não precisamos de um perfil pra navegação ali. Temos isso na guia status e temos o navegação"* | `:55` |
| A área que ensina os gestos mora na Navegação, e ali se configura o que cada conjunto faz | *"talvez aquela seção que fica em emulação e serve também pra ensinar o user fosse mais jogo trazermos ela pra cá e permitir que o user escolha o que cada conjunto faz."* | `:65` |
| O desenho das 5 luzes dá lugar à escolha do número do jogador | *"hoje temos os LEDs ATIVOS (que é uma função placeholder besta). Isso dará lugar à função ESCOLHA O VALOR DO PLAYER daquele controle."* | `:79` |
| A aba Lançadores nasce placeholder e só existe quando o resto estiver pronto | *"essa aba em si só vamos desenhar e deixar placeholder mesmo. E ela só passa a existir quando tiver todas as features no projeto integrando e funcionando."* | `:80` |
| Os cards da aba Controles: todos empilhados; ao escolher um na fita, só ele abre | (verbatim no CSV) | `:82` |
| Plugins aparecem onde o efeito deles chega, sem seção própria | *"eles entram em cada canto que são chamados dentro da GUI. Veja o caso que temos do nome dos jogos na aba Perfis."* | `:85` |
| Toda frase de diagnóstico diz o quê, por quê e o que fazer — e o "o que fazer" vira dica | *"toda frase de diagnóstico diz o quê, por quê e o que fazer"* | `:86` |
| Estilo de Jogo pré-aplica um perfil inteiro | *"no campo estilo de jogo tem que aparecer o campo pra selecionar o jogo, assim como temos pra steam, e temos que ter na aba jogo também"* | `:54` |
| Nenhum perfil pode ter o mesmo número — duas peças nunca têm a mesma cor | *"nenhum perfil pode ter o mesmo número"* | `:56` |
| O combo PS+R3 existe desde 19/08 e nunca apareceu na interface | *"segurar o botão ps e o start faz ele pular de modo de sincronização"* | `:51` |
| Informação que se repete em abas diferentes tem de estar em sincronia | *"a aba status deveria funcionar em sincronia com a aba emulação assim como qualquer informação que se repete em abas diferentes."* | `:50` |
| O topo da aba Perfis avisa quando um perfil nunca vai entrar | *"2 perfis nunca vão entrar — veja quais"* | `:74` |
| O "Modo avançado" **some da interface inteiro**, com os três campos crus. **Ela redesenhou em vez de escolher entre as opções** | (registrado no CSV como redesenho dela) | `:47`; `docs/process/2026-08-26-O-REDESENHO-as-dez-abas.md:710` e `:754` |

**Sem verbatim recuperado, mas com linha no CSV** (17 decisões de 26/08):
`:52` a escolha do player mora na Lightbar · `:58` sprint velha é DESATIVADA, não
apagada · `:61` a aba Configurações vira **Conexões** · `:64` Point-and-click é
Estilo de Jogo · `:66` as dez abas e seus nomes · `:67` o produto funciona fora
da Steam · `:68` a Emulação renasce como **Lançadores** · `:69` o perfil
**Universal** · `:70` catorze estilos de fábrica · `:71` o quinto degrau da roda
PS+R3 · `:72` a máscara ganha "Automático" (**CADUCA em 29/08, derrubada pela
medição**) · `:73` tudo que explica vira dica · `:76` cada controle carrega a sua
configuração dentro do perfil · `:77` Jogar é a home, Perfis é a décima · `:83`
as três regiões do touchpad ganham linha **e o daemon passa a dispará-las** (
**não executada** — o portão continua em `daemon/subsystems/keyboard.py:461-465`)
· `:84` "Terminal" vira "Programas" · `:48` cada jogador navega com o seu
controle.

---

## 25/08 · 24/08 · 23/08 · 22/08

| data | o que ela decidiu | verbatim | CSV |
| --- | --- | --- | --- |
| 24/08 | O MVP é só o DualSense; Pro e 8BitDo voltam na 1.0 | *"Eu tenho eles mas temos que pensar no mvp. o negócio nasceu pra fazer o dualsense funcionar. Vamos completar tudo pro dualsense, depois voltamos neles lá na versão 1.0 e tal."* | `:19` |
| 24/08 | **A aba Conexões MANDA, não avisa** — e toda ordem carrega selo de procedência em três linhas: `[medido]`, `[especificação de terceiro]`, `[derivado]` | (registrado no CSV) | `:16` — **a decisão delegada de 04/09 (`D-08X-SELO-PROCEDENCIA`) restringiu o selo às linhas não medidas, e as duas ordens estão vivas: a GTK obedece a esta, a interface nova à outra** |
| 24/08 | A aba Conexões entra na 0.9.5 e redefine o degrau | *"o rádio para de mentir"* | `:18` |
| 24/08 | A aba diz **"entrada"**, não "porta" | (sai da frase dela) | `:21` |
| 24/08 | O aparelho entra no quadrado por clique-em-clique, não por arrasto | — | `:20` |
| 24/08 | O mapa físico das portas é desenhado e arrastado por ela | — | `:15` |
| 24/08 | A versão sobe em degraus, esquema de quatro níveis | — | `:14` |
| 24/08 | A caixinha do microfone sai dos controles e vira a entrada da conta de slots | — | `:17` |
| 24/08 | Uma caixinha de microfone por controle presente, mais "cabe mais um" | *"Cabe mais um controle com microfone: sim — ficaria em N de 1600"* | `:22` |
| 24/08 | O que a aba diz para quem nunca desenhou a mesa | *"Você ainda não desenhou a sua mesa. Enquanto isso eu digo o caminho do sistema (3-1.1.4) em vez do número da sua entrada."* | `:23` |
| 24/08 | Os cinco degraus do Orçamento viram um perfil de desempenho | — | `:24` |
| 25/08 | Microfone, alto-falante e giroscópio **nascem ligados** em todo jogo ativo | *"Sons do jogo"* | `:37` |
| 25/08 | A calibração de entradas serve de desculpa para olhar a saúde do computador | *"vai servir pra desculpa de olharmos a saúde do seu computador"* | `:39` |
| 25/08 | O par de entradas vem do **desenho dela**, não do sysfs — ela reverteu a própria escolha do mesmo dia, e a medição lhe deu razão | — | `:44` |
| 25/08 | Duas réguas respondem "qual controle move para qual adaptador" | — | `:40` |
| 25/08 | O motor guarda os três números do rádio arredondados | — | `:41` |
| 25/08 | A calibração de entradas entra na leva | — | `:42` |
| 25/08 | A altura da aba Emulação: o que cede em 1080p | — | `:43` |
| 25/08 | O mapa mostra o dongle mudado de lugar sem mandar ninguém movê-lo | — | `:45` |
| 23/08 | A ordem da leva: transversal primeiro, abas depois | — | `:11` |
| 23/08 | O mapeamento de Bluetooth é trilha dela | — | `:12` |
| 23/08 | Prova de tela: o que passa sem o olho dela e o que espera por ele | — | `:13` |
| 23/08 | **As decisões dela encabeçam o painel** — a origem deste registro | *"talvez encabeçar isso na nossa specs pra eu ir vendo junto contigo."* | `scripts/gerar-painel.py:138`, `tests/unit/test_o_painel_encabeca_as_decisoes_dela.py:7` |
| 22/08 | As cinco entregas de largura aprovadas com a janela maximizada | — | `:26` |
| 22/08 | O E-9 autorizado até P2 sem ela na mesa; o P3 só com ela presente | — | `:27` |
| 22/08 | O vigia do Steam Input avisa só quando há problema | *"Saúde do sistema"* | `:28` |
| 22/08 | "steam" e "Steam" saem do perfil Navegação | — | `:29` |
| 22/08 | Semear só os perfis de jogo que faltam, com desfazer do lote | — | `:30` |

---

## As três delegações — o que NÃO é decisão dela

Ela delegou decisão três vezes, e as três estão escritas em
`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md:9-14`:

| quando | palavra dela |
| --- | --- |
| 25/08 | *"vc tem via specs e projeto tudo o que é necessário pra tomar todas as decisões"* |
| 04/09, madrugada | *"não precisa me perguntar mais nada. já sabe o suficiente pra decidir por mim"* |
| 04/09, tarde | *"estude o projeto sozinho. entenda tudo. Depois seja o po e orquestrador e todas as sprints restantes"* |

Sob esses mandatos foram tomadas **70 decisões** que estão no
`docs/data/decisoes-dela.csv` — **54 delas em 04/09, uma por linha aberta das dez
abas** (`D-01J-*`, `D-02C-*`, … `D-10P-*`). Elas são decisões legítimas e estão
registradas. **Não são palavra dela**, e é por isso que ficam fora das tabelas
acima: foi a mistura das duas naturezas na mesma coluna do mesmo arquivo que
permitiu que uma delegação de 04/09 revogasse, sem lápide, o cadeado que ela
mandou sair em 26/08, o botão de reenvio que ela cortou em 27/08 e o custo da
máscara Xbox que ela mandou apagar em 31/08.

**Enquanto o registro não distinguir `quem_decidiu` (a peça C1 do conserto),
este arquivo é a única superfície onde essa distinção existe.**
