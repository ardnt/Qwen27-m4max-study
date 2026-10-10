# Oracle provenance

The test-only reference is extracted from Splash `runtime/model/Model.hpp`
(types) and `runtime/model/DraftContextPlan.cpp` (`planDraftContext`) in the
qualified historical source rooted at commit
`0d5a035ea26d1cc566e3c7ee4e08e5e06fa68cf7`.
Only the named execution-limit constant is replaced by its value, 2048, to
remove Metal headers. The function body is otherwise unchanged. This is a
window-accounting oracle, not a GPU or state-restoration correctness test.
Apache-2.0; see the repository LICENSE, NOTICE and UPSTREAM-SPLASH-NOTICES.

Original complete files SHA-256:

- `Model.hpp`: `c9fb3da6781a55cfb7b38f0bbc8aecb6ef99cf8ab62cf52e3ef431f9bd4bbe6f`
- `DraftContextPlan.cpp`: `ddf997a015417f50e31fea53fc0f96e8b20c68f5c85634dd49b2ca873e8d5535`
