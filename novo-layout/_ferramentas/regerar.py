#!/usr/bin/env python3
"""Regera as DEZ abas de uma vez, contra o MESMO desenho.

Por que existe: cada aba congela o `ds_limpo.svg` da hora em que foi gerada.
Enquanto o desenho está sendo redesenhado, gerar uma aba de cada vez deixa a
mesa com controles diferentes em abas diferentes — foi o que ela viu em 27/08:
a Navegação (12:10), a Vibração (11:56) e a Jogar (00:00) carregavam três
versões distintas, e a Iluminação uma quarta.

A JOGAR GANHOU GERADOR EM 29/08/2026, e este arquivo encolheu por causa disso.
Ela era a única das dez escrita à mão, e daqui saía um remendo de 90 linhas que
trocava o desenho dos cartões, a caixa de máscara de cada um e a frase da
legenda — três coisas que num gerador não precisam de troca. O preço de não ter
gerador estava medido e pago: a cura do logotipo de 28/08 chegou a UMA das dez
páginas, 30 linhas do esqueleto compartilhado não existiam nela, e a folha de
estilo tinha duas cópias mantidas à mão, divergentes em nove blocos. O porquê,
com os números, está no cabeçalho do `aba01.py`.

Uso:  regerar.py            # as dez
      regerar.py 04 06      # só essas
"""
import pathlib, subprocess, sys
import monta

F = pathlib.Path(__file__).resolve().parent
D = F.parent

if __name__ == "__main__":
    quais = sys.argv[1:] or [f"{n:02d}" for n in range(1, 11)]
    for n in quais:
        subprocess.run([sys.executable, str(F / f"aba{n}.py")], check=True, cwd=F)

    # O desenho pode ter mudado NO MEIO da volta: quem redesenha grava o
    # `ds_limpo.svg` a qualquer momento, e o `monta` o lê uma vez só, na importação.
    agora = (F / "ds_limpo.svg").read_text()
    if agora != monta.DS:
        sys.exit("\nATENÇÃO: o ds_limpo.svg mudou durante esta volta.\n"
                 "As abas ficaram com desenhos diferentes de novo — rode outra vez.")
    print(f"\nas {len(quais)} abas contra o MESMO desenho ({len(monta.DS)} bytes)")
