# As páginas finais do todo (a fusão de 14/10/2026)

Uma página por aba, nesta pasta, com tudo o que foi aprovado nas duas branches: a r3 (`voo/mockups-ajustes-r3`: a
rodada 3, os ajustes r3 e r3b, as seis respostas q1 e q2, a v3 c1, n1, n2 e n3) e a r4 (`voo/mockups-rodada-4`: a
rodada 4, os ajustes r4, as seis respostas q4, q5 e q6, a v3 c3 e n4). É o que a sprint zero lê. O detalhe de cada número
está no `NN-mudancas.json` da página («antes» = o todo das rodadas anteriores; as da r4 trazem `n_na_rodada_4`). As
cópias de `rodada-4/` viraram um aviso com o link para cá. A régua é `regua-final.py` (0 falhas nos três tamanhos).

| aba | arquivo | as mudanças, pelo número, e de onde veio cada uma |
| --- | --- | --- |
| 01 Jogar | `01-jogar.html` | 1–11 antes; 12 r4 («O jogo vê», que saiu nos ajustes r4); fusão: as vagas 3 e 4 dizem «P3 • Desconectado» |
| 02 Controles | `02-controles.html` | 1–15 antes; 16 r3; 17 r4 («O que chega», que saiu nos ajustes r4); 18 r4 (alvos e a vaga da q4); a mira virtual da c3; fusão: sem o nome «Vitória» na faixa |
| 03 Gatilhos | `03-gatilhos.html` | 1–14 antes; 15 r3 (com r3b, q1, c1, n1, n2) |
| 04 Iluminação | `04-iluminacao.html` | 1–10 antes; 11 r3; fusão: «P3 • Desconectado», o Cosmic Red sem nome de pessoa, a nota da troca só por `#troca` |
| 05 Vibração | `05-vibracao.html` | 1–11 antes; 12 r3 (com r3b); fusão: «P3 • Desconectado», o Cosmic Red sem nome de pessoa |
| 06 Navegação | `06-navegacao.html` | 1–25 antes; 26–27 r3 (com r3b); 28 r4 |
| 07 Experimental | `07-lancadores.html` | 1–28 antes; 29–37 r3 (com r3b, q2, n3); 38–39 r4 (as 34 e 35 da rodada 4, no diálogo `#acessorios`) |
| 08 Conexões | `08-conexoes.html` | 1–12 antes; 13–17 r3; 18 r4 (a 13 da rodada 4); fusão: «P3 • Desconectado», o rádio embutido pela cor do plástico, o nome de quem joga vazio |
| 09 Sistema | `09-sistema.html` | 1–11 antes; 12 r4 |
| 10 Perfis | `10-perfis.html` | 1–18 antes; 19–20 r3 |
| Calibrar giroscópio | `calibrar-sensores.html` | 1–6 antes; 7 r4 (com q4, q5, q6, n4); fusão: o cartão diz a cor do plástico no lugar do nome de quem joga |
| Mapa das portas | `mapa-das-portas.html` | 1–4 antes; 5–8 r4 |
| Mapa do controle | `mapa-do-controle.html` | 1–18 antes; 19–21 r3; 22–23 r4 (as 19 e 20 da rodada 4) |
| Mapa do rádio | `mapa-do-radio.html` | 1–5 antes; fusão: cada aparelho pela cor do plástico, sem nome de pessoa |

`07-lancadores-b.html` é a leitura B recusada (r3-07-34): fica no git, fora do índice.

## As disputas resolvidas

Vence a resposta mais recente: a v3 > as seis > r4 e r3b > r3.

- **Mapa do controle, o seletor dos moldes:** a r3-21 (os quatro moldes num grupo) e a r4-19/20 (o grupo «Moldes» e,
  abaixo, «Meus perfis» com Orpheus e Maid) mexiam no mesmo seletor. Vence a r4: o grupo «Moldes» com as opções da
  r4 (22) e «Meus perfis» (23); fica o `#sequencia` da r3. A lista `PERFIS` é a da r4, sem o `"square":"Ctrl"` da r3.
- **Conexões, a linha do giroscópio:** a r4-13 é a mesma ideia da r3-17; entra como 18, e o CSS dela também esconde a
  mira no terceiro cartão.
- **Experimental:** a 34 e a 35 da rodada 4 já eram números da r3; viraram 38 e 39. Os dois `<style>` que caíam no
  mesmo ponto entram juntos.
- **A vaga sem controle (q4B) contra a r3-04-11 e a r3-05-12:** a r3 pedia a vaga sem o nome do controle; a q4B diz o
  quê: «P3 • Desconectado» e «P4 • Desconectado», sem cor de plástico. Vale na 01, 02, 04, 05, 08 e na Calibrar.
- **A q1 na 03:** a linha do alto não mostra os desconectados; ali não há vaga para dizer «P3 • Desconectado».
- **A 06:** o «Navega com» só lista os conectados; não há vaga na página.
- **A 04 rolava (1122 px em 809):** a nota do antes e depois ficava fora da janela; agora só abre por `#troca`.
- **O nome de pessoa:** «Vitória», «Pedro», «Ana», «Rafa» e «Lia» viraram a cor do plástico de cada controle (05, 02,
  04, 08, Mapa do rádio); o campo de quem joga nasce vazio, com a dica «Nome de quem joga» (08), e o cartão da Calibrar diz a cor do plástico na linha do nome. No Mapa das
  portas, «Jogador 1» a «Jogador 4» ficam: é o número do jogador, não «Player». A citação sua na nota da 04 («o meu
  controle azul é o player 2») fica, como toda citação sua.

## As quatro dúvidas da v3, decididas por delegação (14/10/2026, a validar por você)

1. O nome comprido do estilo desce para uma terceira linha, e a linha do alto cresce ~15 px sem desalinhar a grade.
2. A dica do «Mira virtual» basta.
3. O L2 vem escolhido no segundo seletor.
4. Os botões da face aparecem pelo símbolo (✕ ○ □ △), com o nome na dica.
