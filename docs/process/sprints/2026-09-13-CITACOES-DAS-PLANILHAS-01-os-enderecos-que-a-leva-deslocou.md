---
sprint: CITACOES-DAS-PLANILHAS-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  CITACOES-DAS-PLANILHAS-01:
    - docs/data/paridade-gtk-html.csv
    - docs/data/mapa-controles.csv
    - docs/data/decisoes-dela.csv
    - html/specs.html
    - docs/process/sprints/2026-09-13-CITACOES-DAS-PLANILHAS-01-os-enderecos-que-a-leva-deslocou.md
cria: []
bancada: false
depois_de:
  # 13/09/2026: é a última coisa da leva. Toda sprint da onda 2 desloca linhas
  # que as planilhas citam, e a SISTEMA-BOTOES-01 escreve a paridade.
  - SISTEMA-BOTOES-01
  - RECONECTAR-SAMBA-02
  - MIC-SEM-FONTE-01
  - DICA-DA-COR-01
  - SENSORES-NO-JOGO-02
  - FRASES-E-DICAS-03
  - F1-REMAPEAR-02
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
---

# CITACOES-DAS-PLANILHAS-01 — os endereços que a leva deslocou

Nasceu na costura da onda 1 (13/09/2026). A validação da FRASES-E-DICAS-02
contou ([entrega](../agentes/2026-09-13/FRASES-E-DICAS-02-opus.md)): das 294
citações `arquivo:linha` das planilhas que apontam para os oito arquivos de
`src/` daquela sprint, **185 caem hoje noutra linha** (79 na
`a08_conexoes.py`, 59 na `a02_controles.py`, 29 na `secao_controles.py`), quase
todas em `docs/data/paridade-gtk-html.csv`. O portão `citacoes-de-linha` só
cobra as que prometem símbolo; as outras envelhecem caladas. A onda 2 desloca
mais.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| Só se reaponta a citação cuja âncora é inequívoca; a que não tem âncora vai para a entrega com o contexto, sem número chutado | a regra da casa de reapontar por símbolo, nunca por aritmética (o comentário das 27 que saíram em 10/09, em `tests/unit/test_portao_o_par_com_metade_ligada.py`) |
| Roda depois da onda 2 costurada, sobre a base que vai para o `dev` | a mesma regra: reapontar citação é a última coisa |
| Nenhum script novo no repositório: o roteiro fica no rascunho e a entrega traz o comando | o §0 do índice (enxugar) |

## §I — IMPLEMENTA

1. Para cada `caminho:linha` e `caminho:a-b` das três planilhas que aponta para
   um arquivo desta árvore:
   * achar o commit em que aquele texto de citação entrou na planilha (o mais
     antigo do `git log -S` na planilha);
   * ler a linha citada no arquivo daquele commit, e procurá-la no arquivo de
     hoje;
   * igual na mesma linha: fica. Achada UMA vez noutra linha: reaponta (numa
     faixa, cada ponta pela sua âncora). Zero ou várias: não mexe, e vai para a
     entrega com a planilha, a linha e o texto da âncora;
   * linha em branco ou só pontuação (`)`, `"""`) não é âncora.
2. `scripts/gerar-mapa.py` regera `html/specs.html` depois do mapa, e o
   `--check` confere.
3. `scripts/validar-citacoes-de-linha.py --all` e o portão
   `citacoes-no-codigo` seguem verdes.

## §V — Prova

* A contagem, antes e depois: quantas conferiam, quantas foram reapontadas e
  quantas ficaram sem âncora.
* Mordida: desfazer uma reapontada e rodar o roteiro de novo, que a acusa; trocar
  um número bom por um vizinho, que ele acusa também.
* Dez reapontadas conferidas à mão pelo símbolo, listadas na entrega.

## §R — O preço

Uma âncora que hoje existe duas vezes fica sem reapontar. É o preço de não
chutar.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** / **no perfil** / **por controle** | não se aplica: a sprint só mexe em endereço de documentação |
