# Your research library

A new checkout contains no personal scientific knowledge, learned skills, or reusable analysis methods. The library is local to this workspace and is not populated from another user's wiki. The application stores assets here as research produces them; it never publishes them externally automatically.

- `wiki/`: literature observations and scientific statements, with sources, applicability and review state.
- `skills/`: method-selection and checking guidance. Skills refer to methods; they do not grant permissions or contain a second implementation.
- `methods/`: reusable analysis methods. Each method has one current implementation, its interface description and exact-source validation references.

The application uses one catalog interface for these kinds. Each asset has a current head and immutable metadata versions. Candidate, reviewed, contested and superseded states are distinct. An edit returns a reviewed asset to candidate. Historical metadata is evidence, not an alternative installed method.

Run-local exploratory code belongs to its project. A method becomes reusable only after the trusted application records validation of that exact code and a review decision. Model confidence or a successful process exit is not a scientific validation. The library records these decisions; execution authority remains with the existing control plane.

Local references must identify files under `projects/` or `library/` by workspace-relative path and SHA-256. Literature references contain a URL and an original-source locator. Changing an asset does not silently rewrite dependent research: dependencies remain pinned and changed dependencies are displayed for re-examination.

Framework upgrades must preserve this directory. The source framework is under `src/lqcd_agent/`; acquired research assets never modify that execution authority. Users choose whether to version or share their library in their own Git workflow.

From the workspace root, create a candidate with `lqcd-agent library-save --kind wiki --id correlation --title 'Correlation note' --body-file notes/correlation.md --scope '{"observable":"ratio"}' --source-url https://example.org/paper`. Source URLs entered this way identify the document; they do not claim a specific passage was checked. The text remains a candidate until an explicit review decision.

Use `library-search` to inspect current text, applicability and review states. `library-review --kind wiki --id correlation --status reviewed --rationale 'Checked the stated conditions' --expected-revision 1` records the operator's decision in an immutable receipt under `reviews/`. Evidence arguments refer only to project files. Editing reviewed content returns it to candidate and requires the current revision.

Methods first need a candidate description. `library-register-method` then requires a project Python source, one or more project validation JSON files, an explicit rationale and the expected revision. Each validation file must bind `source_sha256` to that exact source and contain `passed: true` plus nonempty named passing `checks`. Registration checks this evidence and Python syntax; it never executes the source or proves that the supplied numerical checks are scientifically adequate. The operator must evaluate that evidence before making the review decision. The code and receipt are retained with the method's provenance.
