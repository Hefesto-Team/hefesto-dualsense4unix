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

## 02-controles.html
- **19/09/2026** — A-LUZ-DO-MIC-ESPELHA-O-BOTAO-01, a metade da TELA da decisão
  dela. O bloco do Microfone ganhou a linha que diz **quem está te ouvindo**
  («Ninguém está te ouvindo ainda.»), e a dica do `?` passou a dizer que a luz
  **acesa** quer dizer *ligado*, não *alguém te ouve*.

  **Por que a linha teve de nascer:** no mesmo dia a luz do controle passou a
  espelhar o BOTÃO (`daemon/subsystems/luz_do_mic.decidir`), e com isso ela
  deixou de distinguir sozinha *"ligado"* de *"ligado e alguém te ouvindo"* —
  o `0` queria dizer duas coisas, e foi lendo a luz apagada que ela desligou o
  próprio microfone achando que o ligava.

  **Medido antes de desenhar** (Chrome headless, janela do produto de 1180px):
  o card aberto vai de **329,6 a 351,9 px** com a linha escrita e o
  `.quadro-corpo` **não passa a rolar**; a frase cabe em UMA linha na coluna
  de 281 px, e o dono dela troca os nomes pela contagem antes de deixar a
  linha dobrar.

  **O QUE O PRODUTO FAZ ATÉ ELA PUBLICAR, e é o contrato desta seção:** a
  metade do DAEMON já vale (é código, não desenho) — a luz do controle
  **acende** com o microfone ligado, sem depender de app nenhum. O pacote já
  emite o campo `mic-ressalva` em todo tique, mas a página publicada não tem
  esse endereço: até publicar, o valor cai no vazio, sem erro e sem pixel, e
  **a aba dela continua exatamente como está hoje** — luz certa no plástico,
  nenhuma linha dizendo quem ouve. Nada de clique morto nem de texto vazando:
  o que falta é a linha, e ela só nasce com o OK dela.
