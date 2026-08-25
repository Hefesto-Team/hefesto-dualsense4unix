# Por que USB 3.0 atrapalha 2,4 GHz — a fonte da afirmação

- **Levantado em:** 25/08/2026
- **Por que existe:** o produto afirma, em **quatro** lugares, que USB 3.0 emite
  ruído em cima da faixa de 2,4 GHz — e não dizia de onde tirou isso. Autoridade
  anônima é exatamente como raciocínio se veste de medição, e esta casa tem selo
  de procedência justamente para impedir isso. Esta página é o **dono** da
  afirmação: o selo `especificacao-de-terceiro` de R1
  (`integrations/ordens_da_mesa.py`) aponta para cá, e há teste que reprova se o
  arquivo sumir.
- **Limite de escopo, declarado antes de qualquer afirmação:** **nada aqui foi
  medido nesta bancada.** Esta página cita terceiro, e só. A medição que fecharia
  o ganho de afastar o rádio de banda larga desta máquina é a **W1** da sprint
  ORDEM-DE-SERVIÇO-01 §9, e é **dela**.

---

## 1. A fonte

> **USB 3.0\* Radio Frequency Interference Impact on 2.4 GHz Wireless Devices**
> Intel Corporation, white paper, documento **327216-001**, abril de 2012.
> Publicado também pela USB-IF: <https://www.usb.org/document-library/usb-30-radio-frequency-interference-impact-24-ghz-wireless-devices>

O que ela afirma, e que é o que o produto repete:

| afirmação | o que a fonte diz |
|---|---|
| há ruído | a sinalização de dados de um conector USB 3.0 acrescenta ruído **de banda larga** ao ambiente |
| quanto | da ordem de **20 dB** acrescentados na faixa de 2,4 GHz |
| onde | o ruído alcança a faixa de **2,4 a 2,5 GHz** — que é a faixa ISM dos controles |
| por quê | o embaralhamento obrigatório dos dados da especificação USB 3.0 espalha a energia em vez de concentrá-la em raias estreitas |

## 2. O grau desta página, e ele não é "medido"

**GRAU: `especificacao-de-terceiro`.** E dentro dele, o grau da minha
conferência, que é menor do que eu gostaria e por isso está escrito:

- o documento **existe**, o número e a data conferem, e ele é publicado pela
  USB-IF e pela Intel — os dois endereços acima;
- **eu não li o PDF nesta sessão.** As duas tentativas de baixá-lo (usb.org e
  intel.com) responderam **HTTP 403**. O conteúdo da tabela acima vem de
  resumo de busca, não do documento aberto;
- portanto: **a existência e a identidade da fonte estão conferidas; os números
  da tabela estão corroborados, não verificados na fonte primária.**

Quem abrir o PDF e conferir os números: corrija a tabela aqui e **substitua** —
número errado não é decisão a preservar, e sai de todos os lugares onde aparece.

## 3. O que esta página NÃO autoriza a dizer

Ruído existir **não** é ruído estar atrapalhando a máquina dela. As duas
afirmações estão a uma medição de distância, e a medição não foi feita:

1. **não** se pode dizer que o aparelho de 5 Gbps está derrubando o Bluetooth
   dela — é hipótese, e é a W1 da §9 que a fecharia;
2. **não** se pode prometer ganho por afastar o aparelho. Por isso a terceira
   linha de R1 diz "não medi o ganho nesta máquina", e diz sempre;
3. **não** se pode citar milímetro, altura de antena ou linha de visada. Esses
   números são raciocínio do `GUIA-RADIO-DA-SALA.md`, não desta fonte.

## 4. Onde a afirmação aparece no produto

Os quatro lugares que esta página passa a cobrir:

| onde | o quê |
|---|---|
| `integrations/ordens_da_mesa.py` | a linha `por_que_importa` de R1, com `fonte=` apontando para cá |
| `integrations/mesa_de_radio.py` | o comentário de `_VELOCIDADE_USB3` |
| `app/actions/config/secao_mesa.py` | a dica `_DICA_USB3_AO_LADO` da seção A mesa |
| `docs/usage/interface.md` | a frase da seção Conexões |

Só o primeiro tem `fonte=` hoje. Dar dono aos outros três é varredura de texto de
tela, e o texto desta aba tem uma frente dona única
(CONFIGURACOES-O-LEXICO-01) — **não** se edita aqui, ou duas frentes escrevem a
mesma frase.
