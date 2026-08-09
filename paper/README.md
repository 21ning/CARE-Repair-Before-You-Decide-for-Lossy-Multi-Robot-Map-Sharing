# Anonymous ICASSP paper package

Compile `care_icassp_draft.tex` from this directory with an IEEEtran-enabled
LaTeX installation. The repository includes the final figures and concise
derived tables used to audit the paper's numerical claims, including the final
six-loss/eight-baseline CARE matrix, its A*/D* Lite comparison, the
cross-planner deadline matrix and Periodic Full Anti-Entropy (K=4) control.

The raw 100-map episode outputs are not bundled in the submission code
repository. They can be regenerated from the frozen code and configurations
documented in `../docs/REPRODUCIBILITY.md`; the runners write only to explicit,
empty output directories.
