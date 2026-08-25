"""Quem aplica a escala de fonte NO PROCESSO tem de usar a régua declarada.

O DEFEITO, MEDIDO EM 25/08/2026
--------------------------------

Oito arquivos de teste medem a janela com a escala de fonte aplicada de
verdade — sem isso, ~90% da tela mediria os 13,33px padrão do Pango e os
números não seriam os da janela real. Para aplicá-la, todos mexem em
``Gtk.Settings.get_default()``, que é **singleton do processo**.

Sete deles liam a escala com ``escala_fonte()``, que consulta o
``gui_preferences.json`` **de quem roda**. Nesta bancada, ``escala_fonte: 6``.
Disso saem dois estragos, e o segundo é o caro:

1. **o teste muda de veredito sem o produto mudar** — o mesmo arquivo passa na
   escala padrão e reprova na escala dela;
2. **a escala VAZA para os arquivos seguintes da mesma sessão do pytest.** As
   fixtures são ``scope="module"``: quem roda primeiro deixa o singleton na
   escala dela, e quem roda depois mede na escala errada achando que mede na
   sua.

Foi assim que ``test_layout_orcamento_altura.py`` reprovava DOIS testes dentro
de um lote e passava sozinho — a janela "pedia 1236px" contra um teto de
1180px, e os 56px de diferença eram a escala 6 vazando de
``test_largura_a_mesma_em_todas_as_abas.py``, que a coleta põe logo antes
("largura" vem antes de "layout").

**Nenhum dos dois estava errado sobre o produto.** Era o instrumento
respondendo coisas diferentes conforme o que rodara antes — a
``O-INSTRUMENTO-MENTE-MAIS-QUE-O-PRODUTO`` desta casa, desta vez pela porta da
ORDEM de execução, que é a mais difícil de ver: sozinho, cada arquivo passa.

POR QUE ESTE PORTÃO EXISTE, E NÃO SÓ A CORREÇÃO
------------------------------------------------

A correção já tinha sido feita **uma vez**, em 25/08, em
``test_layout_orcamento_altura.py`` — com um comentário longo explicando
exatamente este raciocínio. E ficou em **um arquivo de oito**. Os outros sete
continuaram lendo a escala de quem roda, e o defeito que a correção descreve
seguiu vivo por escrito, ao lado da própria explicação de por que ele é ruim.

É a regra desta casa na forma mais cara: *fato errado se substitui em TODOS os
lugares onde aparece; correção pela metade deixa as duas versões vivas.*
Portão é o que transforma "corrigi onde vi" em "não volta".

O QUE ESTE PORTÃO **NÃO** PROÍBE
---------------------------------

``escala_fonte()`` continua livre para quem só a LÊ — testar a própria função,
conferir o que a preferência dela devolve, medir sem tocar no singleton. O que
o portão cobra é de quem **aplica** ao processo: aí a régua tem de ser a
declarada, porque a medida deixa de ser só sua.

A MORDIDA
---------

Troque ``delta = ESCALA_PADRAO`` por ``delta = escala_fonte()`` em qualquer
uma das fixtures e ``test_quem_aplica_a_escala_usa_a_regua_declarada`` reprova,
nomeando o arquivo e a linha.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "tests" / "unit"

#: Quem CHAMA isto está escalando o nome da fonte para aplicá-lo ao processo.
#:
#: A primeira versão desta régua procurava a string ``"gtk-font-name"``, e era
#: LARGA DEMAIS: ela acusava cinco arquivos que só CITAM a propriedade em
#: docstring e comentário — um deles justamente para explicar que RESTAURA o
#: valor. É o mesmo defeito que esta casa mediu em 25/08 noutro portão, onde
#: uma frase de tela desligava a varredura: **contar palavra em prosa como se
#: fosse chamada**. A régua desliga (ou grita) exatamente quando alguém escreve
#: uma explicação boa.
#:
#: ``escalar_nome_da_fonte`` é a função que de fato compõe o nome escalado, e
#: só quem vai APLICAR a chama. Medido: casa os oito arquivos que aplicam, e
#: nenhum dos cinco que só falam do assunto.
APLICA_NO_PROCESSO = "escalar_nome_da_fonte"

#: A régua declarada: a escala com que o produto NASCE em quem instala.
REGUA_DECLARADA = "ESCALA_PADRAO"

#: A leitura da preferência de quem roda. Livre para ler, proibida para aplicar.
LEITURA_DE_QUEM_RODA = re.compile(r"^\s*delta\s*=\s*escala_fonte\(\)\s*$", re.M)


def _aplica_no_processo(texto: str) -> bool:
    """O arquivo compõe um nome de fonte escalado — logo, vai aplicá-lo?

    Casar pela CHAMADA e não pelo nome da propriedade é a correção medida
    (ver a nota em `APLICA_NO_PROCESSO`): a propriedade aparece em prosa, a
    chamada não.
    """
    return APLICA_NO_PROCESSO in texto


def arquivos_que_aplicam() -> list[Path]:
    return sorted(
        p
        for p in UNIT.glob("test_*.py")
        if p.name != Path(__file__).name and _aplica_no_processo(p.read_text(encoding="utf-8"))
    )


class TestAEscalaNaoVazaEntreArquivos:
    def test_a_regua_acha_quem_aplica(self) -> None:
        """Guarda do instrumento: régua que não acha ninguém passa sempre.

        Se a varredura voltar vazia, o teste abaixo fica VERDE por não olhar —
        e esta casa já pagou por um portão tautológico (`ids.issubset(ids)`).
        """
        achados = arquivos_que_aplicam()
        assert len(achados) >= 5, (
            f"a varredura achou só {len(achados)} arquivo(s) que chamam "
            f"`{APLICA_NO_PROCESSO}`. Eram OITO em 25/08/2026. Se eles "
            "sumiram de verdade, baixe o piso com nota datada; se a régua é "
            "que parou de enxergar, ela virou tautologia e o portão abaixo "
            "está verde sem medir nada."
        )

    def test_quem_aplica_a_escala_usa_a_regua_declarada(self) -> None:
        """O portão."""
        culpados: list[str] = []
        for p in arquivos_que_aplicam():
            texto = p.read_text(encoding="utf-8")
            for m in LEITURA_DE_QUEM_RODA.finditer(texto):
                linha = texto[: m.start()].count("\n") + 1
                culpados.append(f"{p.relative_to(RAIZ)}:{linha}")

        assert not culpados, (
            "estes arquivos APLICAM a escala em `Gtk.Settings` (singleton do "
            "processo) e leem o delta de `escala_fonte()`, que é a preferência "
            "de QUEM RODA:\n"
            + "\n".join(f"  {c}" for c in culpados)
            + f"\n\nDois estragos, os dois medidos em 25/08/2026: o teste muda "
            "de veredito conforme a escala de quem roda, e a escala VAZA para "
            "os arquivos seguintes da mesma sessão (as fixtures são "
            "`scope=\"module\"`). Foi assim que dois testes de layout "
            "reprovavam em lote e passavam sozinhos.\n"
            f"O conserto é uma linha: `delta = {REGUA_DECLARADA}`.\n"
            "Se este arquivo PRECISA medir na escala dela, ele precisa do "
            "próprio teto — é outra pergunta, não a mesma com resposta móvel."
        )

    def test_quem_aplica_importa_a_regua(self) -> None:
        """Coerência: quem aplica tem de ter a constante à mão.

        Sem esta linha, um arquivo poderia "passar" no portão acima por não
        definir `delta` nenhum e aplicar um número solto — que é pior, porque
        some da varredura E da explicação.
        """
        sem_regua = [
            str(p.relative_to(RAIZ))
            for p in arquivos_que_aplicam()
            if REGUA_DECLARADA not in p.read_text(encoding="utf-8")
        ]
        assert not sem_regua, (
            "estes arquivos aplicam a escala no processo e não citam "
            f"`{REGUA_DECLARADA}` em lugar nenhum — provavelmente aplicam um "
            "número solto, que não aparece em varredura nem em explicação:\n"
            + "\n".join(f"  {c}" for c in sem_regua)
        )
