# As abas em trabalho na bancada

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ela ainda não deu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** A bancada é o desenho de hoje; o produto
só recebe quando ela aprova a aba **inteira**, que é a escolha dela de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto nela.
```

Quando ela aprovar a aba, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## 09-sistema.html

- **02/09/2026** — **o bloco "O serviço" estourava 27px com os valores REAIS**,
  e o desenho nunca mostrou isso porque os textos dele são curtos. `.bloco2`
  usava `1fr` cru, que tem por piso o CONTEÚDO: quando a linha "Como ele
  enxerga a janela" deixou de dizer `Wayland · COSMIC` (literal do desenho) e
  passou a dizer `Sem ver nada agora (sem_foco_x)` (o que a máquina dela
  responde), a coluna de estado não encolheu, empurrou os quatro botões e eles
  atravessaram o risco por cima do Perfil de Bateria.

  Medido no Chrome (1920×1080), na página **publicada**, com os valores que o
  pacote emite hoje — o bloco vizinho começa em `x=973`:

  | valores | os botões ocupam | resultado |
  | --- | --- | --- |
  | os do desenho | `[748..932]` | folga de 41px |
  | os reais, com `1fr` | `[816..1000]` | **estouro de 27px** |
  | os reais, com `minmax(0,1fr)` | `[748..932]` | folga de 41px |

  Com os textos do desenho a cura **não muda um pixel** (as duas primeiras
  linhas da tabela dão a mesma caixa). O que ela muda é a aba com dado de
  verdade dentro.

- **02/09/2026** — **o mesmo defeito, de novo, em `.saude-cols`, e 253px.** As
  frases do `storm_report` são longas (*"regra áudio-off inativa — o mic e o
  fone do controle estão liberados. O que fazer: nada."*) e as do desenho são
  curtas. Com `1fr` cru a coluna não encolhe, as reticências de
  `.saude .txt span:last-child` nunca chegam a agir, e a segunda coluna do
  exame passa por cima de "Preparar os jogos". Medido na bancada, `x=1263` é
  onde aquela faixa começa:

  | achados | a 2ª coluna termina em | resultado |
  | --- | --- | --- |
  | os do desenho | `1222` | folga de 41px |
  | os reais, com `1fr` | `1516` | **estouro de 253px** |
  | os reais, com `minmax(0,1fr)` | `1222` | folga de 41px |

  **A régua desta aba passou a cobrir `.bloco2` e `.saude-cols`** (`aba09.py`,
  régua 5): ela cobria as três faixas EXTERNAS e deixava as internas de fora —
  e o `1fr` cru ficou invisível ali por não estourar com texto de bancada.

- **02/09/2026** — **o exame ganhou endereço** (`data-campo` + `data-hef-alvo`
  em `exame-contagem` e `exame-lista`). São atributos invisíveis, não mudam um
  pixel, e estão nesta seção só porque as mudanças de CSS acima já a abriram.
  Enquanto o exame não tinha endereço, a janela mostrava os OITO achados de
  bancada deste gerador — *"Steam Input estava ligado em 2 jogos — desliguei"*,
  *"Proton fixado em 9.0-4 para 3 jogos"*, *"8 linhas · nenhum aviso"*. Nenhum
  aconteceu: o `storm_report` desta máquina devolve **seis**, e outros seis.

**Publicar as duas:** `scripts/check_o_desenho_aprovado.py --publicar 09`.
