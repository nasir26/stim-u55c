# paper/

Self-contained submission package for the stim-u55c research paper,
targeting Springer's *Journal of Supercomputing*. Every number, table,
and figure here is transcribed directly from this repository's own
`docs/utilization.md` and `bench/results/*.md` -- see the paper's own
Appendix A for the exact mapping.

## Contents

- `main.tex` -- the paper. Springer Nature `sn-jnl` class, `sn-basic`
  reference style (numbered, bracketed citations).
- `sn-jnl.cls`, `sn-basic.bst` -- the Springer Nature LaTeX class and
  bibliography style (not on CTAN; bundled here so the folder compiles
  standalone, e.g. on Overleaf, with no extra package installation).
- `sn-article.tex` -- Springer's own unmodified example/reference file
  for the class, kept for reference; not part of the submission.
- `sn-bibliography.bib` -- references, in BibTeX format.
- `figures/` -- all figures, as vector PDF (regenerate with
  `make_figures.py`; see below).
- `make_figures.py` -- regenerates every figure in `figures/` from the
  same numbers cited in `main.tex`'s tables (matplotlib, PDF output).
  Run `python3 make_figures.py` from this directory (needs `matplotlib`
  and `numpy`).
- `LICENSE` -- Apache-2.0 license for the Springer Nature template
  files (`sn-jnl.cls`, `sn-basic.bst`, `sn-article.tex`), from
  <https://github.com/DanySK/template-latex-springer-nature-sn-jnl>.
  The paper text and figures are covered by this repository's own
  top-level Apache-2.0 `LICENSE`.

## Building

Upload this entire `paper/` folder to Overleaf (or compile locally):

```
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

No other packages beyond a standard, reasonably complete TeX Live
installation are required.
