# Maintainer's document-level visual review

Date recorded: 2026-09-24.
Reviewer: repository maintainer `fokhruli`, through the BnTeX project conversation.

The maintainer's actual feedback on `bntex-expanded-forms-review.pdf` was:

> looks okay to me

Record this as **general visual acceptance of the demonstrated expanded-form
sheet for continuing development**, not an invented per-case review or release
certification. No case-specific comments, alternate-font judgments, PDF-viewer
tests, accessibility checks, or malformed-input approvals were supplied.

## Artifact binding

- PDF filename: `bntex-expanded-forms-review.pdf`
- SHA-256 of the actual conversation attachment:
  `6836a7c70f09297c449f959b0eec3b54bf9db725495eb24fdd867c26b93b4be0`
- Associated implementation: PR #11, head
  `0877465587bbc484efa02cf5bf8657ba90f868d4`.
- Expanded supplementary oracle SHA-256 recorded by that PR:
  `9466f84a8117d992b034392ba4992e1d745e31c67561160153e67cb49753782f`.
- Pinned Noto Serif Bengali Regular SHA-256:
  `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.

The PDF hash was measured directly from the provided attachment. The oracle and
font identities are taken from the associated PR's provenance, not derived by
extracting embedded fonts from the PDF. No font or PDF binary is committed here.

The per-entry review ledgers remain unchanged. Their schema requires distinct
attributed entries, and the maintainer did not provide 261 separate judgments.
This note acknowledges the review that actually occurred and does not pretend
that no human feedback has been received. The remaining review/release scope of
issue #3 is a separate maintainer decision; this implementation does not close it.

The subsequent instruction authorized the recommended decoder milestone. It did
not authorize a merge into main, changing repository visibility, or publication.
