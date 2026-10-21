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
- **21/10/2026** — espera só o `--publicar 01`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 01`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 02-controles.html
- **21/10/2026** — espera só o `--publicar 02`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 02`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 03-gatilhos.html
- **21/10/2026** — espera só o `--publicar 03`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 03`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 04-iluminacao.html
- **21/10/2026** — espera só o `--publicar 04`: a regra `.criar .meu.conta` do chip «Seus efeitos: N», a variante A aprovada em 20/10 (O-ILUMINACAO-NAO-ROLA-COM-OS-EFEITOS-CRIADOS-01). O pacote já pinta o chip único com os nomes na dica, então enquanto isso o produto mostra o chip sem a regra (o `cursor:help` e o `nowrap`), e a aba não rola.
- **21/10/2026** — espera só o `--publicar 04`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 04`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 05-vibracao.html
- **21/10/2026** — espera só o `--publicar 05`: o «Parar» do «Testar agora» com fundo e borda `#c62828` e a letra branca (5,62 para 1), a variante A aprovada em 20/10 (O-PARAR-DA-VIBRACAO-SE-LE-NO-VERMELHO-01). Enquanto isso, o produto continua com o «Parar» no `--red`.
- **21/10/2026** — espera só o `--publicar 05`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 05`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 06-navegacao.html
- **21/10/2026** — espera só o `--publicar 06`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 06`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 07-lancadores.html
- **21/10/2026** — espera só o `--publicar 07`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 07`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 08-conexoes.html
- **21/10/2026** — espera só o `--publicar 08`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 08`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 09-sistema.html
- **21/10/2026** — espera só o `--publicar 09`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 09`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.

## 10-perfis.html
- **21/10/2026** — espera só o `--publicar 10`: a barra de baixo (Aplicar, Salvar perfil, Importar, Exportar) e o chip da fita «Selecionar» que se clica respondem ao mouse, pelas regras `:hover` do `topo.html` (o desenho aprovado em 20/10, A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01). Enquanto isso, no produto nada muda sob o mouse.
- **21/10/2026** — espera só o `--publicar 10`: o fundo e o aro da logo viram os tokens `--logo-fundo` e `--logo-aro` (sem tema, nada muda na tela; o tema claro religa o disco escuro, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Enquanto isso, o produto pinta a logo sem fundo também com o tema.
