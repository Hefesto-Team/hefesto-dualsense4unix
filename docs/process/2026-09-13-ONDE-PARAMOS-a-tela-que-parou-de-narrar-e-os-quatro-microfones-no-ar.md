# ONDE PARAMOS — 13/09/2026: a tela que parou de narrar e os quatro microfones no ar

## §0 — O estado em uma linha

**`dev` em `e58bfe2b`, instalado às 05:30 com `rc=0` (daemon reiniciado às
05:29:52, `doctor` sem nenhuma FALHA) · 60 portões verdes medidos às 05:00, ANTES
do `e58bfe2b` — esse commit acrescentou uma linha em `a10_perfis.py` e deixou o
`citacoes-no-codigo` vermelho no `dev` empurrado; a triagem da tarde achou, e a
citação foi reapontada por símbolo · a suíte inteira verde nas 24 partes (20.369
testes).** A leva seguinte — a terceira lista dela —
está em `docs/process/sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`.

## §1 — O que ela pediu nesta sessão, com as palavras dela

> *"quero que na aba perfis vc mesmo toque os ajustes os demais manda agentes."* <!-- noqa-acento: citação literal dela -->
>
> *"essas frases de status que aparecem no rodapé isso não deveria estar aparecendo. também. preciso que remova isso tambem."* <!-- noqa-acento: citação literal dela -->
>
> *"em todas as abas da interface"*
>
> *"essses bugs graficos natela sao muito comuns."* — *"botoes que mudam de lugar direto."* <!-- noqa-acento: citação literal dela -->
>
> *"sim prosv 4 mesma coisa com o autofalante"* <!-- noqa-acento: citação literal dela -->
>
> *"integra tudo tá o install completo e reinicia o daemon ao final fora o push em dev viu? nao to jogando agora. entao pode mandar ver."* <!-- noqa-acento: citação literal dela -->

## §2 — O que entrou

| frente | o que ela vê | commit na `onda/1309` |
| --- | --- | --- |
| a guarda que congelava a janela | a janela deixou de ficar presa no literal do mockup («perfis antigos», «2 controles», clique e lupa mortos) | `71c69c57` |
| aba Perfis (quem coordena, por ordem dela) | a tira calada; a frase vai ao `interface.log` | `48c01271` |
| MIC-O-CANAL-DO-OUTRO-01 | o microfone não pega o canal de outro controle; o órfão sai; o `pactl` mudo ganha recuo | `71d36fae` |
| FLAKE-DO-PISCA | a régua do pisca espera o pouso, não o relógio | `6c61cdb6` |
| TELA-CALADA-02 | o cartão da Steam diz o estado («2 jogos sem o atalho»), não a história | `bd6adbea` · `19eae268` |
| TELA-CALADA-03 | Sistema pergunta no painel; Conexões para de narrar a espera | `3f98b4b7` |
| TELA-CALADA-01 | o sucesso não deposita recado em aba nenhuma; a recusa fica só na aba em que nasceu | `41f10f9a` |
| JOGAR-A-FAIXA-QUE-PULA-01 | o «Reconectar controles» não muda mais de lugar; a faixa da Jogar para de falar | `87d4bd0c` |
| SOM-RECUO-01 | som e volume dividem o recuo do microfone e param de martelar o servidor de áudio mudo | `8dd04fe9` |
| OS-QUATRO-NO-AR-01 | os quatro microfones ficam no ar juntos; perder o padrão não é sair do ar; o som já era por controle | `06b2631e` |
| a costura | a régua da 01 mede a página sem faixa; a citação da aba Perfis volta ao símbolo | `8d51f9b2` · `678b8964` |

**O «botão que muda de lugar», medido pela JOGAR-A-FAIXA-QUE-PULA-01:** não era o
texto da pendência nem a largura. Era o recibo do Reconectar pousando
INVISÍVEL na mesma fileira (vestia `.pendente`, que a faixa esconde) e empurrando
o botão 223 a 301 px para a esquerda. As fotos dela de 02:48 são um recibo curto e
um longo.

## §3 — As armadilhas deste dia

1. **O agente para esperando o aviso da tarefa de fundo — cinco de sete.** O
   aviso não chega, e o agente fica parado com os portões rodando. O conserto é
   de quem coordena: achar o PID vivo pelo `cwd` da árvore e mandar esperar em
   primeiro plano por `kill -0 <pid>`, nunca por `pgrep`.
2. **E o conserto errado custou uma corrida duplicada.** Quem coordena mandou
   «se não terminou, rode de novo» sem conferir o processo; o agente disparou a
   segunda corrida na mesma árvore, e a primeira teve de ser morta por PID — a
   `bash` do `portoes.sh` sobrevive ao `SIGTERM` e segue para o portão seguinte.
   **Confira o processo ANTES de mandar rodar de novo.**
3. **Duas entregas certas, costuradas, deram um vermelho.** A TELA-CALADA-01
   exigia a faixa de recado da 01 como prova de medição; a JOGAR-A-FAIXA a
   tirou. Nenhuma das duas via a outra — é o *conferente isolado não vê a
   integração* de novo.
4. **Uma mordida mal montada passou verde.** A sabotagem chamou o depósito com a
   assinatura de ontem (três argumentos, hoje são quatro) e a régua da tela não
   reprovou. Refeita com a assinatura certa, reprovaram três. **Mordida que não
   reprova pede primeiro conferir que a sabotagem rodou.**
5. **Um teste da aba 07 lia o `/proc` da máquina.** Com um jogo da Steam aberto,
   quatro testes reprovavam na base e na integração, iguais. Curado na régua
   (`19eae268`).
6. **O scratchpad da sessão é compartilhado entre os agentes**, e o
   `scripts/sanitizar_saida_de_agente.py` trata um ARQUIVO de destino como pasta.
   Um script de mordida de um agente foi sobrescrito pelo de outro.

## §4 — O que é dela

* **A luz do microfone com dois no ar.** Com um app gravando só do padrão, a luz
  do outro controle apaga no plástico (contrato da LUZ-DO-MIC-01, *aceso =
  alguém ouvindo*), embora o microfone dele esteja no ar. Mantido como está.
* **A ALTURA-DA-VISTA-01**, entregue em `87de2f54` e não costurada: a altura
  segue a vista e a faixa do logotipo sai. Muda a proporção da janela — é o olho
  dela.
* **O adaptador Bluetooth da porta USB 1-4** (TP-Link UB500, `hci0`) reinicia a
  cada ~2,5 s desde o boot; não segura controle nenhum. Hardware.
* **A prova de aparelho** dos quatro microfones e do recuo do som: MESA-DE-QUATRO-01.

## §5 — A fila

1. **TELA-CALADA-04** (aberta): a recusa de gesto sem coluna ganha piscada
   própria no botão e para de cobrir o cartão do P1; o tom `sucesso` sem
   depositante sai; o painel da 09 para de mostrar o diário com `uniq=`; a
   pergunta que envelhece aos 20 s.
2. **Os `pactl` fora do recuo:** `app/audio_saida.py`, `app/mic_monitor.py`,
   `integrations/eleicao_de_microfone.py`, `quem_ouve_o_microfone.py`,
   `canal_do_microfone.py`, `hotkey.py`. O molde é
   `audio_control._rodar_pelo_recuo`.
3. **O som não tem varredor de órfão**, e o `iniciar` do som não pergunta se o
   `sink_name` já existe.
4. **Prosa e dados que envelheceram** (fora das posses da leva): a célula
   `audio.microfone@dualsense` do mapa, `sentinela_do_wrapper.frase_do_aviso_curta`,
   `carona_do_wrapper.ResultadoDaCarona.frase_curta`, `docs/data/paridade-gtk-html.csv`,
   `docs/data/donos-de-comportamento.csv`, `docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md`,
   `dualsense_bt_audio._talvez_seguir_a_source`, `recado_do_microfone.GESTOS`.
5. **A causa do travamento do servidor de áudio** depois da queda do controle
   (01:53, 47 minutos mudo): nenhuma das curas impede, só param de agravar.
