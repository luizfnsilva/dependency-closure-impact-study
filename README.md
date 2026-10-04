# dependency-closure-impact-study

Continuous-integration runs of a pre-registered software-engineering study of failures of dependency-closure
change impact analysis on time-zone data (IANA tz) and C builds (zlib, Lua).

- **Protocol:** Zenodo, DOI [10.5281/zenodo.23138643](https://doi.org/10.5281/zenodo.23138643) (restricted while the
  associated manuscript is under review; opened on editorial decision). It was deposited together with the frozen code
  before any oracle run on the sampling frame.
- **Frozen code:** `experimento/`. Every file has its SHA-256 recorded in `experimento/config.json` (`modulos`).
  Before reading any commit pair, the runner refuses to start (exit code 2) if:
  - any file differs from its recorded hash;
  - the toolchain differs (gcc, cc1, make, zic and zdump binaries by SHA-256; dpkg versions; Python series);
  - the wheels differ (`networkx`, `pygments` by hash);
  - the DOI is absent.
- **Trigger:** `.github/workflows/oraculo.yml` runs only for the commit that introduces the DOI in `experimento/config.json`.
  It can also be dispatched by hand to resume an interrupted run. The workflow then runs:
  - the oracle and the analysis arms for each corpus;
  - a re-execution of 10% of the records on a second machine, compared byte by byte.
- **Outputs:** `experimento/saidas/<corpus>.jsonl` is hash-chained and committed by the runner as it goes. The provider's
  run logs are the third-party timestamp of the first output.

Author: Luiz F. Nunes da Silva (ORCID 0009-0002-5409-7074).
