# Decision: Documentation Versioning Strategy

**Date**: 2026-01-06
**Context**: GraphRAG MCP Server with constitution v1.0.0
**Full Research**: See [research-versioning.md](research-versioning.md)

---

## Decision: Latest + Git Tags (with future migration path)

### Rationale

**Why this fits initial needs**:

- **Current Stage**: System in active development, constitution just ratified (v1.0.0). Complex multi-version documentation is premature for early-stage project.

- **Resource Constraints**: Small team with limited bandwidth. Maintaining multiple documentation versions would divert effort from feature development and quality improvements.

- **Deployment Model**: Server deployed as remote HTTP service (Railway). Users don't control their version—they use whatever is deployed. Reduces need for version-specific docs.

- **Audience**: Technical users (developers, integrators) who can navigate git tags when needed. Don't require polished version switcher UI yet.

- **Constitutional Alignment**: Extends existing date-stamped optimization pattern in troubleshooting.md to entire documentation state via git tags.

---

### Implementation

#### How Versions Are Managed

**Current Documentation** (primary):
- Lives in `docs/` directory on `main` branch
- Always reflects latest system state
- Updated concurrently with code changes
- Validated against live system (95% success rate target)

**Historical Snapshots** (fallback):
- Git tags mark documentation states at releases: `v1.0.0`, `v1.1.0`, etc.
- Tags aligned with constitution versions or major features
- GitHub releases link to documentation at that tag
- No separate version branches or directories

**Versioning Rules**:
- Tag format: `v{MAJOR}.{MINOR}.{PATCH}` (semantic versioning)
- Tag on constitution version changes or major feature releases
- Include documentation link in GitHub release notes
- Track breaking changes in CHANGELOG.md

**Example Workflow**:
```bash
# Tag a release
git tag -a v1.0.0 -m "Release v1.0.0: Constitution v1.0.0"
git push origin v1.0.0

# Create GitHub release
gh release create v1.0.0 \
  --title "v1.0.0 - Constitution Ratification" \
  --notes "Documentation: [View at v1.0.0](https://github.com/ArthurSrz/graphRAGmcp/tree/v1.0.0/docs)"
```

---

#### How Users Switch Versions

**Latest Documentation** (recommended):
- Navigate to repository docs/ or deployed documentation site
- Always current, always validated

**Historical Documentation** (when needed):
- **Via GitHub Web**: Go to Releases → Select version → Click tag → Browse `docs/`
  - Example: https://github.com/ArthurSrz/graphRAGmcp/tree/v1.0.0/docs

- **Via Local Git**:
  ```bash
  git checkout v1.0.0
  mkdocs serve  # View docs at v1.0.0
  git checkout main  # Return to latest
  ```

**Version Discovery**:
- Version badge in README: "Documentation for v1.0.0"
- Notice in docs/index.md: "Looking for older versions? See [Releases](https://github.com/...)"
- CHANGELOG.md lists version history

**No Version Switcher** (intentionally):
- Signals "use latest unless you have specific reason"
- Reduces maintenance burden
- Encourages users to upgrade

---

### Future Evolution

#### When to Add Full Multi-Version Support

**Move to Mike Plugin (Phase 2) when**:

Any **2 of these triggers** occur:

1. **Constitution v2.0.0+**: Breaking changes requiring parallel v1/v2 documentation
2. **User Base >50 Active Integrators**: Support burden from version confusion increases
3. **LTS Release Model**: Need to maintain v1.x and v2.x simultaneously
4. **Support Burden >40%**: Documentation version questions dominate support tickets
5. **Community Request**: External contributors open PRs requesting version switcher

**Metrics to Track**:
- GitHub release page views (historical doc interest)
- Support ticket tags: "documentation-version-confusion"
- Time spent backporting doc fixes (>2 hours/month signals need)
- User feedback surveys on documentation clarity

**Migration Effort**:
- Initial setup: 4-8 hours
- Per-release overhead: +1-2 hours
- Requires mike plugin, CI/CD updates, version support policy

**Migration Path**:
```bash
# When triggered
pip install mike

# Import existing tags
mike deploy 1.0.0 --push
mike deploy 1.1.0 --push
mike deploy 2.0.0 latest --push --update-aliases

# Add version switcher to mkdocs.yml
```

---

#### Cost-Benefit Threshold

**Benefit**: Multi-version support provides value when **>30% of users** are on non-latest versions

**Cost**: Adds ~2 hours/release + backport effort + CI complexity

**Decision Rule**: When cost of version confusion exceeds maintenance cost, migrate to Phase 2

---

## Summary

| Aspect | Current Approach | Future State |
|--------|------------------|--------------|
| **Strategy** | Latest + Git Tags | Mike Plugin Multi-Version |
| **Trigger** | Now (v1.0.0) | When 2+ triggers met |
| **Complexity** | Low | Medium-High |
| **Maintenance** | Minimal | 2+ hours/release |
| **User Experience** | Simple (latest focus) | Excellent (version switcher) |
| **Best For** | Early-stage, rapid iteration | Mature, LTS releases |

---

**Next Steps**:
1. Add version badge to README.md
2. Add version notice to docs/index.md
3. Create CHANGELOG.md
4. Tag current state as v1.0.0
5. Document tagging procedure in CONTRIBUTING.md
6. Monitor trigger conditions for Phase 2 migration

**Full Research**: See [research-versioning.md](research-versioning.md) for detailed analysis of all options (Mike, Git Tags, Single Version, Hybrid Archive).
