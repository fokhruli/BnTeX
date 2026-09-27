# BnTeX development plan — navigation

Current entry points take precedence over the dated bootstrap snapshot:

1. [Automatic authoring](docs/AUTOMATIC-AUTHORING.md): wrapper-free `bntex-auto`,
   audited regular/bold fonts, standard formatting and declared synthetic slant.
2. [Roadmap](docs/ROADMAP.md): current work and remaining acceptance gates.
3. [Overleaf handoff](docs/OVERLEAF-NATIVE.md): project-local installation and the
   still-pending actual browser/new-word-edit procedure.
4. [Explicit integration](docs/NATIVE-INTEGRATION.md): optional legacy interfaces,
   source manifests, memoization and their scoped historical measurements.
5. [Release readiness](docs/RELEASE-READINESS.md): mechanical checks and unresolved
   evidence; no CTAN/PyPI publication or visibility change is authorized.

Design and learning references:

- [Architecture](docs/ARCHITECTURE.md), [native shaper design](docs/NATIVE_SHAPER.md)
  and [profile audit](docs/PROFILE_AUDIT.md) document the implementation's origins.
- [Learning](docs/LEARNING.md), [testing](docs/TESTING.md) and [CTAN](docs/CTAN.md)
  provide exercises and review requirements.
- [Bootstrap validation](docs/BOOTSTRAP-VALIDATION.md) and the original full plan
  are historical; current results belong to the exact revision's PR/CI evidence.

Issues #15 and #25 now prioritize automatic input and styles. Earlier deferrals
do not override the maintainer's new request. The repository exists privately at
`fokhruli/BnTeX`; fonts and public releases are not distributed by these guides.
