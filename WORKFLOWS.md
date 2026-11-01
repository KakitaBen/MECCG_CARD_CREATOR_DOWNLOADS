# Preparing application and illustration releases

Use the manual workflows in this repository's **Actions** tab. Software and
illustration collections have separate forms and independent versions.
All source selections require the full, validated 40-character commit from the
private source repository. No workflow publishes a release automatically.

## Build application installers

The application workflow has only two fields:

| Field | Meaning |
| --- | --- |
| `source_commit` | Exact source commit to build. The version comes from its `VERSION.txt`. |
| `illustrations_version` | Already published independent collection, for example `1.00`. |

This workflow packages the common resources, builds all four program targets,
and verifies Windows, Linux, and macOS installers. It does not download artwork
from Git LFS or depend on an older software release for illustrations.
The collection manifest is pinned by version, size, and SHA-256.

After every required job succeeds, review the draft release before publishing
it manually. Published releases cannot be replaced. A new source tag is not
required to start this workflow.

## Prepare illustration collection

Use this workflow after changing artwork in the private source repository.

| Field | Meaning |
| --- | --- |
| `source_commit` | Validated source commit containing the artwork changes. |
| `collection_version` | New independent revision, for example `1.01`. |
| `previous_collection` | Published collection to compare with, for example `1.00`. |

Only this workflow explicitly downloads source artwork from Git LFS. It reuses
unchanged lots from the previous collection and prepares changed lots with their
verified inventories and indexed ZIP files. After successful preparation,
publish the collection draft manually. Do not mark it as the latest software
release. Referenced older illustration collections must remain available.

The initial migration from software release `v0.60.31` to illustration collection
`1.00` is complete. Its `collection_base` and `resources_version` fields have
been removed from the forms. Historical migration remains available only as an
explicit maintenance command in `tools/delivery.py`.

## Verify Windows installer

The separate diagnostic workflow takes `source_commit` and `release_version`.
Use the same source commit as the original build and an existing **draft**
software release. It repeats the useful Windows installer checks, including
Unicode installation paths, silent installation, option persistence, opt-out,
application startup, and HTTPS. It refuses to replace a published installer.

## Safety and runs already in progress

All workflows share the `public-delivery` concurrency group and do not cancel a
running delivery. Changing the forms does not alter an already dispatched run.
Private source is checked out without persistent credentials; detailed build
logs stay on the runner. Public failure diagnostics remain limited to a step
name and a non-sensitive error category.

The push-triggered runner check still runs the orchestration tests on changes to
workflows, tools, or tests. The former `check_only`, `windows_only`, and
`collection_only` switches are no longer needed in the application form.
