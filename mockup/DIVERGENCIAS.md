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

## 01-jogar.html
- **27/10/2026** — a Jogar junta os controles: o quadro Status (Ligado, Desligado, Reconectar e Modo Freestyle na mesma linha, os modos Sony DualSense, Xbox e Nintendo Pro com a silhueta de cada um) e, embaixo, os Dispositivos conectados da antiga Controles. Sai o «O controle é visto como» (o quadro e a máscara na linha de cada controle) e o Point and click. Aberto: o daemon e a ponte não conhecem o gesto `modo-nintendo` nem o modo único para todos os controles. Até publicar, o produto continua com a Jogar de hoje, o quadro do «visto como» e a aba Controles.

## 02-controles.html
- **27/10/2026** — a página deixa a tira e vive dentro da Jogar; o Calibrar giroscópio ganhou o glifo do giroscópio. Até publicar, o produto continua com a Controles como aba própria e o Calibrar sem glifo.

## calibrar-sensores.html
- **27/10/2026** — o «Fechar» e o «Voltar» levam à Jogar, porque a Controles saiu da tira. Até publicar, o produto continua levando à Controles, que ainda é aba própria.
- **27/10/2026** — a página embute a letra das abas (Space Grotesk e JetBrains Mono, do pacote). Até publicar, o produto continua com a letra do sistema.

## mapa-das-portas.html
- **27/10/2026** — a página embute a letra das abas (Space Grotesk e JetBrains Mono, do pacote). Até publicar, o produto continua com a letra do sistema.

## mapa-do-radio.html
- **27/10/2026** — a página embute a letra das abas num `<style>` próprio, depois da folha que a aba Conexões lê. Até publicar, o produto continua sem o `@font-face` e cai na letra do sistema onde a Space Grotesk não está instalada.

## 03-gatilhos.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.
- **27/10/2026** — o efeito do gatilho abre com «Do estilo» e os grupos de um efeito só se juntam (Rajada, Pulso, Clique); o desenho do controle fica ao lado do «Estilo de jogo», sem o rótulo «Controle»; o criador parte da Metralhadora e mostra só as barras que a base escolhida manda ao gatilho. O produto já conhece o «Do estilo» e os grupos novos (`efeitos_de_imersao.FAMILIAS_DA_PAGINA`, gesto `imersao`). Até publicar, a página publicada continua com o criador de quatro barras sempre à mostra; a folga da etiqueta «Rajada» já entrou na publicada.

## 04-iluminacao.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.
- **27/10/2026** — a linha entre «Modelo» e «Cor» fica só na coluna dos rótulos, e o «Criar efeitos novos» sai. Até publicar, o produto continua com o criador da luz.

## 05-vibracao.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.
- **27/10/2026** — a linha entre «Modelo» e «Força da vibração» fica só na coluna dos rótulos; a de «Testar agora» sai das colunas dos controles; o «Sensor háptico» para em 100 %, como os motores; a «Força da vibração» ganha o trilho largo e o polegar rosa; o «Criar efeitos novos» sai. Aberto: o daemon guarda o ganho da háptica até 200 % (`HAPTICA_PCT_MAX`) e nasce em 150 %. Até publicar, o produto continua com o trilho de 0 a 200 e o criador da vibração.

## 06-navegacao.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 07-lancadores.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 08-conexoes.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 09-sistema.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 10-perfis.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N USB · N BT» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.
