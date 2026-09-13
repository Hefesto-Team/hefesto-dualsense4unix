---
sprint: TELA-CALADA-04
estado: absorvida
onda: A-FILA-DE-1309
posse:
  TELA-CALADA-04:
    - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
    - src/hefesto_dualsense4unix/interface/aba05.py
    - mockup/05-vibracao.html
    - src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html
    - src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py
    - src/hefesto_dualsense4unix/app/actions/daemon_actions.py
cria:
  - tests/unit/test_a_recusa_sem_coluna_pisca_no_botao.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
  - src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py
  - src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py
---

# TELA-CALADA-04 — a recusa sem coluna, o verde sem dono e o painel que fala jargão

> **ESTADO 13/09/2026 (tarde): absorvida**, antes de qualquer agente, pelo
> estudo da terceira lista dela. As §1 e §2 entram na
> [FRASES-E-DICAS-01](2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md)
> — **com duas correções**: a recusa COM coluna também sai do cartão (a caixa da
> foto dela é essa), e a frase NÃO vai ao `title` (a camada da dica da casa
> mostra todo `title` como caixa flutuante, e a frase da Steam voltaria por ali).
> As §3 e §4 entram na
> [SISTEMA-BOTOES-01](2026-09-13-SISTEMA-BOTOES-01-cada-botao-da-aba-sistema-faz-o-que-diz.md),
> que escreve o mesmo `a09_sistema.py`. O teste do `cria:` abaixo nasce com outro
> nome, na FRASES-E-DICAS-01.

**13/09/2026.** O que as entregas da TELA-CALADA-01 e da TELA-CALADA-03 deixaram
de pé, com o endereço. A palavra dela que move a leva é a mesma:

> *"essas frases de status que aparecem no rodapé isso não deveria estar aparecendo. também. preciso que remova isso tambem."* <!-- noqa-acento: citação literal dela -->
>
> *"em todas as abas da interface"*

## §1 — A recusa de gesto que não mora em coluna

**Medido pela TELA-CALADA-01** (entrega de 13/09, «O que sobrou», item 1): a
recusa do cadeado, do Reconectar, do modo da 01, do rodapé e do gabinete da 08
pousa no cartão do controle apontado pela fita e cobre o nome dele por 30 s. O
pouso do botão NÃO distingue recusa: o recorte do botão depois do pouso é byte a
byte igual ao de antes do clique.

**O desenho (decidido por quem coordena, por delegação dela; reversível):**

1. `voltouDoVoo(n, certo=false)` passa a acender uma piscada de RECUSA no botão
   — classe própria, mesma duração da piscada verde (`MS_DA_PISCADA`), com a cor
   de aviso da paleta. Sem texto.
2. A frase da recusa vai ao `title` do botão até o próximo clique nele e ao
   diário (`[gesto falhou] …`, que já existe).
3. **Gesto sem ancestral `[data-controle]` não pousa recado em cartão nenhum.**
   A recusa de gesto de coluna continua no cartão da própria coluna, como hoje.

## §2 — O tom `sucesso` ficou sem quem deposite

Desde a TELA-CALADA-01 nenhum gesto deposita sucesso, e o que servia a ele
continua de pé: `SEGUNDOS_DO_RECADO_DE_SUCESSO` e o ramo de prazo em
`_recados_para_a_tela`, o `COR_DO_SUCESSO` do BOOTSTRAP, e a faixa
`data-hef-recados="sucesso"` do `#vib-estado` da 05 (`aba05.py` → mockup →
`--publicar 05`; a da 01 já saiu na JOGAR-A-FAIXA-QUE-PULA-01). As réguas que
cobram esse canal mudam de contrato **com data e citação**, nunca apagadas em
silêncio (a entrega da TELA-CALADA-01 lista três). A prosa que ainda descreve o
canal verde em `a03_gatilhos.py`, `a04_iluminacao.py` e `a05_vibracao.py` não é
desta posse: liste os endereços na entrega.

## §3 — O painel da aba Sistema fala jargão sem ninguém clicar

**Medido pela TELA-CALADA-03:** `_repouso_do_painel` mostra o `systemctl status
--no-pager`, que emenda as últimas linhas do diário do daemon — com `uniq=` e o
endereço inteiro. O funil do piloto acusa `[texto banido] 'uniq'` a cada abertura
da 09. O painel em repouso responde *«está ativo? desde quando? falhou?»*: sem as
linhas do diário (`systemctl status -n 0`, ou o equivalente pelo dono), e a
identidade de fábrica continua por último. O «Ver detalhes», que ela pede, fica
como está.

## §4 — A pergunta que envelhece

**Medido pela TELA-CALADA-03:** aos 20 s o consentimento vence, o botão volta ao
rótulo do desenho e o painel continua dizendo «Clique de novo para confirmar» até
o próximo clique — e o mesmo acontece se ela armar outro gesto destrutivo. A
pergunta sai do painel quando o consentimento dela vence ou passa a outro gesto.
Meça o preço que a entrega apontou (o censo das camadas sumir junto) e escolha o
caminho que não o apaga.

## §5 — O que morde

* Recusa do cadeado com dublê: nenhum `.hef-recado` em cartão; o botão veste a
  classe de recusa e a perde em `MS_DA_PISCADA`; o `title` tem a frase. Arrancar
  → reprova.
* Recusa de gesto de coluna continua no cartão dela.
* A 05 publicada não declara `data-hef-recados`.
* Painel da 09 em repouso sem `uniq` e sem linha de diário. Arrancar → reprova.
* Pergunta armada e vencida → painel sem a pergunta no tique seguinte.
* Piloto `--oculta`: foto do botão recusado, da 05 e da 09, antes e depois.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | não se aplica: é a tela |
| **no perfil** | nada vai ao disco |
| **por controle** | a recusa de coluna segue no cartão do controle; a sem coluna não pousa em nenhum |
