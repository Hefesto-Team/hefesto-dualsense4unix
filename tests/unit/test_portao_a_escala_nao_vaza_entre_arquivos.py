"""Quem aplica a escala de fonte NO PROCESSO tem de usar a régua declarada."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "tests" / "unit"

APLICA_NO_PROCESSO = "escalar_nome_da_fonte"

REGUA_DECLARADA = "ESCALA_PADRAO"

LEITURA_DE_QUEM_RODA = re.compile(r"^\s*delta\s*=\s*escala_fonte\(\)\s*$", re.M)


def _aplica_no_processo(texto: str) -> bool:
    """O arquivo compõe um nome de fonte escalado — logo, vai aplicá-lo?"""
    return APLICA_NO_PROCESSO in texto


def arquivos_que_aplicam() -> list[Path]:
    return sorted(
        p
        for p in UNIT.glob("test_*.py")
        if p.name != Path(__file__).name and _aplica_no_processo(p.read_text(encoding="utf-8"))
    )


class TestAEscalaNaoVazaEntreArquivos:
    def test_a_regua_acha_quem_aplica(self) -> None:
        """Guarda do instrumento: régua que não acha ninguém passa sempre."""
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
        """Coerência: quem aplica tem de ter a constante à mão."""
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
