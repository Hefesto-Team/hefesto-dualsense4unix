# ONDE PARAMOS — 13/09/2026, noite: a terceira lista costurada, o modo que é caminho e o som que não trava na queda

## §0 — O estado em uma linha

**`dev` em `92cd2f0b` mais este documento, instalado às 22:59 com `rc=0` (`doctor`:
tudo OK, com 5 avisos e nenhuma FALHA) · 60
portões verdes em `1a6cc7c8` · a suíte inteira nas 24 partes: 20.741 passaram e 5
reprovaram — três curados na costura, e os dois que sobram são uma régua que
mede a bancada (§5) · empurrado para o `upstream` (Hefesto-Team) junto com este documento, por
fast-forward a partir de `e7d1dac2`.** A leva é a terceira lista dela, e o
[índice](sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md) tem as sprints, as
ondas e onde mora o estado de cada uma.

## §1 — O que ela pediu nesta sessão, com as palavras dela

A lista inteira, verbatim, está no §0 do índice. Depois dela, no mesmo dia:

> *"o modo de conexão do conexão da aba jogar nao ta funcionando. o texto do modo do xbox tá errado aquilo é o texto da mascara do xbox"* <!-- noqa-acento: citação literal dela -->
>
> *"nao esquece do merge em dev, install documentar e push. quando concluir tudo."* <!-- noqa-acento: citação literal dela -->
>
> *"pro hefesto team. na real eu achei que tivessemos sempre mandando pra lá e tivessemos abandonado o meu repo pessoal kkkkkkkk"* <!-- noqa-acento: citação literal dela -->
>
> *"nenhuma chance de ser nosssas configs do hefesto na aba controles na parte do som e microfone? algum bug que causa isso?"* <!-- noqa-acento: citação literal dela -->
>
> *"A INTERFACE AINDA TEM O PEPINO DO MODO E DA MASCARA."* <!-- noqa-acento: citação literal dela -->

A regra dela sobre o modo e a máscara está em
[DECISOES-DELA-O-REGISTRO](DECISOES-DELA-O-REGISTRO.md), na seção de 13/09, e em
`docs/data/decisoes-dela.csv` (`D-1309-O-MODO-E-A-BASE-E-A-MASCARA-VEM-POR-CIMA`).

## §2 — O que entrou

| onda | o que ela vê | na `onda/1309` |
| --- | --- | --- |
| 1 | a caixa laranja e a frase da Steam saem da tela; o install script do Sackboy não finge mais jogo vivo; a luz dentro da Steam deixa de herdar a cor fosca do cliente; a troca de botões do perfil chega ao jogo; a fita para de saltar | `ffaa9154..bae5e1ed` |
| 2 | cada botão da aba Sistema faz o que diz, e o «Ver os plugins» saiu; o «Reconectar» para de pular; as dicas que avisavam viram estado; o ensaio do giroscópio mira a biblioteca que o jogo carrega | até `b791d234` |
| 3 e 4 | os restos das ondas 1 e 2; o fato do zero do giroscópio sai dos lugares que ficaram; as citações das planilhas reapontadas pela âncora | `af6e4af6..06fc9c54` · `b76c80f9..821ef2a5` |
| MODO-DE-CONEXAO-01 | o chip do Modo e o PS + R3 escolhem o caminho («Sony DualSense» é o canal próprio, «Xbox» o canal comum); a máscara do cartão vale na hora, com o jogo aberto; o PS + R3 grava no perfil | `411e186d..622016f9` · `9639f1df`, no `dev` às 18:52, antes do fecho, porque ela ainda via o defeito |
| SOM-TRAVA-NA-QUEDA-01 | o gravador da ponte do rádio morre antes de o nó de som sair, e os três filhos de som têm um dono só | `73e35837..84b03887` |
| A-MARCA-DA-DEGRADACAO-01 | o asterisco que nunca acendia sai das abas 01 e 02, e os dez geradores conferem antes de escrever | `f7235c66..31668d21` |
| a costura do fim | a paridade recontada, com a decisão de 04/09 da marca caduca; as fotos das duas vistas; a prova dos chips de modo | `b834250e` · `368368c7` · `001eaeb5` · `1a6cc7c8` · `92cd2f0b` |

**A resposta à pergunta dela sobre o som:** sim, era do Hefesto, mas não das
configurações da aba Controles. Quando o controle no rádio cai com o
alto-falante do Hefesto de pé, o `pw-record` da ponte ficava preso escrevendo num
cano cheio, o `SIGTERM` ficava pendente, e o servidor de som esperava por ele. A
cura fecha o cano e colhe o processo antes de o nó sair. O elo do wireplumber não
foi medido, e a prova com o controle na mão é da bancada (§4).

## §3 — As armadilhas deste dia

1. **O zsh não parte variável sem aspas.** Um `env $E` virou um argumento só, e o
   piloto de uma validação falou com o daemon dela por 14 s às 18:02 e recriou o
   vpad do P1 — sem jogo aberto, e sem nada a desfazer. Os prompts passaram a
   mandar: comando com ambiente num arquivo de shell rodado por `bash`, um
   `export` por variável e uma guarda que sai com `exit 1`.
2. **A régua que conferia o gesto de antes da cura.** `test_os_botoes_tem_dono`
   exigia `flavor` dos chips de modo; nenhum portão roda esse arquivo, a validação
   da MODO não o alcançou, e só a suíte inteira viu. É o *conferente isolado não
   vê a integração* de novo.
3. **O módulo `csv` reescreve as aspas de uma linha que ninguém tocou.** Gravar a
   paridade inteira mudaria a linha 297. A trava contra o original (linhas
   mudadas iguais às linhas-alvo) recusou antes de gravar, e a edição passou a
   emendar só a linha física.
4. **`--doc` sem `--vista dela` deixa a família maximizada para trás**, e a régua
   das fotos acusa com o commit da família normal. E um commit de código de tela
   depois das fotos pede a segunda porta, `docs/usage/assets/CONFERIDO-EM.txt`,
   quando as vinte saem iguais.
5. **O `PR_SET_PDEATHSIG` é da THREAD que lança, não do processo.** Um filho
   lançado de uma thread curta morre quando ela termina (medido: `rc −9` em
   2,1 ms). Os filhos de som só podem nascer de thread longa.
6. **A internet caiu no meio de uma validação.** O que ela deixou foi guardado num
   commit, e o MESMO papel rodou de novo, com a ordem de commitar cedo.
7. **O push perdeu a corrida para o push dela** (`cannot lock ref`): o hook de
   anonimato leva minutos em mil commits, e ela empurrou no meio. Não é defeito;
   `git fetch` antes do push do fecho.

## §4 — O que é dela (a bancada, MESA-DE-QUATRO-01)

* O modo, a máscara e o PS + R3 com o jogo aberto (§B da MODO-DE-CONEXAO-01).
* Três desligamentos do controle no rádio com o alto-falante de pé e
  `timeout 3 pactl info` em laço noutro terminal (§B da SOM-TRAVA-NA-QUEDA-01).
* O Sackboy com o «0» do Steam Input; e o DON'T SCREAM e o Mullet Mad Jack, que
  podem perder o controle com o «0».
* A luz dentro da Steam e o giroscópio com o jogo aberto.

## §5 — A fila

1. **A régua do berço da aba Config mede a bancada.** Os dois testes de
   `tests/unit/test_config_a_palavra_de_tela_da_aba_montada.py` colhem 172 textos
   contra o piso de 186, porque a seção Conexões lista os aparelhos USB da
   máquina, perto de sete textos por linha. Medido: igual em `9639f1df` e em
   `e7d1dac2`, em três voltas alternadas, e o `e7d1dac2` fechou verde às 05:40. A
   cura é dar ao berço um barramento de mentira, como a fixture de sysfs vazio.
2. **`tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py` pergunta
   `pactl list sinks short` ao servidor de som real:** a guarda do `conftest` só
   barra `load-module` e `unload-module`.
3. **`nivel_do_microfone._FluxoParec.parar`** ainda espera 2 s na ordem velha; o
   dono único, `src/hefesto_dualsense4unix/integrations/filho_de_som.py`, não o
   alcança.
4. **O elo do wireplumber** no travamento do som não foi medido (§D.6 da
   SOM-TRAVA-NA-QUEDA-01).
5. **Da GTK e das réguas velhas:** `profiles_actions._mode_section_from_editor`
   ainda poda a máscara fora do modo jogo;
   `tests/unit/test_game_signal_wiring.py` é intermitente; a docstring de
   `hidraw_broker.physical_nodes_exposure` não tem régua.
6. **Registro:** `scripts/ensaios/a_jogar_diz_quem_e_o_primario.py` foi corrigido
   e não rodado; uma citação de linha histórica em
   `docs/process/2026-09-10-AS-FRASES-QUE-MENTEM-a-tela-medida-contra-o-produto.md`
   ficou velha; o bloco da bancada provisória se repete nos dez `__main__` dos
   geradores.
