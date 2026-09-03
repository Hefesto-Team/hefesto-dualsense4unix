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

## 08-conexoes.html
- **03/09/2026** — `MIGRA-08-01`. **NÃO HÁ DESENHO NOVO AQUI: são DEZ endereços
  de pintura em elementos que já existiam**, e nenhum move um pixel. O
  `so_mudou_endereco()` deste portão confirma: apagados os trinta atributos que
  ele conhece, a única diferença que sobra são os seis `data-hef-quando` dos
  botões da sala — e `data-hef-quando` **não está na lista `INVISIVEIS`**, que é
  defeito do portão, não da página (a `08-conexoes.html` PUBLICADA já usa esse
  atributo, nas cinco pílulas do Check-up).

  Os dez: `ordem` (a coluna da ordem de serviço), `conta-gestao` (a contagem da
  seção), `sala-altura` e `sala-visada` (três botões cada) e `bateria` (um por
  controle). Sem eles o pacote emite e o `achar()` do piloto escreve ZERO,
  calado — a tela dela continua mostrando *"Mova o adaptador Bluetooth da
  Entrada 3 para a Entrada 9"*, que é o desenho apresentado como diagnóstico da
  máquina dela.

  **O caminho barato é `--publicar-enderecos 08`**, e ele só passa a existir
  quando alguém puser `data-hef-quando` (e `data-hef-classe`) na `INVISIVEIS`
  do `scripts/check_o_desenho_aprovado.py` — arquivo de outro dono. Enquanto
  isso, quem integra decide entre fazer aquilo ou `--publicar 08`.
