# Research: Documentation Versioning for GraphRAG MCP Server

**Feature**: 001-system-documentation
**Research Task**: Q4 - Documentation versioning approaches
**Date**: 2026-01-06
**Status**: Complete

## Context

The GraphRAG MCP server has:
- Constitution v1.0.0 (ratified 2026-01-06) that evolves via semantic versioning
- Active development with evolving capabilities
- Need to maintain documentation accuracy as system changes
- Multiple audiences requiring stable reference materials
- No current git tags or version releases

**Research Question**: How should documentation be versioned as the GraphRAG MCP server evolves?

## Research Findings

### 1. MkDocs Versioning with Mike Plugin

**What it is**: Mike is a plugin that manages multiple documentation versions by deploying each version to a separate subdirectory in a git branch (typically `gh-pages`).

**How it works**:
- Each version is built and deployed separately: `mike deploy 1.0.0 latest`
- Versions are stored in git history, not filesystem
- Built-in version switcher dropdown in documentation UI
- Maintains an index of available versions with aliases
- Supports "latest", "stable", "development" aliases

**Advantages**:
- Clean version switching in UI (dropdown selector)
- Each version is immutable once deployed
- Works perfectly with GitHub Pages or static hosting
- Can maintain multiple versions simultaneously (e.g., v1.x, v2.x)
- Version-specific search (searches only current version)

**Disadvantages**:
- Requires separate build/deploy for each version
- Increases storage requirements (full docs per version)
- Complexity overhead for early-stage projects
- Requires discipline to update "latest" and "stable" aliases
- CI/CD needs to know which version to deploy

**Implementation**:
```bash
# Install mike
pip install mike

# Deploy initial version
mike deploy 1.0.0 latest --push --update-aliases

# Deploy new version
mike deploy 1.1.0 latest --push --update-aliases

# Make 1.0.0 stable
mike alias 1.0.0 stable --push

# Set default version
mike set-default latest
```

**Best for**: Mature projects with multiple stable releases requiring long-term support.

---

### 2. Git Tag-Based Versioning

**What it is**: Use git tags to mark documentation states aligned with code releases, with a single "current" documentation version served from main/master branch.

**How it works**:
- Tag releases: `git tag -a v1.0.0 -m "Release 1.0.0"`
- Documentation always reflects latest code state
- Historical documentation accessible via git checkout of tags
- Users can view old docs by checking out tags locally or via GitHub's branch/tag selector

**Advantages**:
- Simple to implement (no additional tools)
- Documentation versioning mirrors code versioning
- Zero maintenance overhead for version switching
- Clear correlation between code version and documentation state
- GitHub automatically creates release pages from tags

**Disadvantages**:
- No in-documentation version switcher
- Users must know to check out tags for historical docs
- Cannot easily view multiple versions side-by-side
- Less discoverable than dedicated version switcher
- Requires rebuilding docs from historical tags to view

**Implementation**:
```bash
# Tag a release
git tag -a v1.0.0 -m "Initial release with constitution v1.0.0"
git push origin v1.0.0

# Create GitHub release (optional)
gh release create v1.0.0 --title "v1.0.0 - Initial Release" --notes "See docs/ for documentation"

# View historical docs locally
git checkout v1.0.0
mkdocs serve  # View docs as they were at v1.0.0
git checkout main  # Return to latest
```

**Best for**: Early-stage projects where latest documentation is primary, occasional need to reference historical states.

---

### 3. Single Version (Latest Only)

**What it is**: Maintain only current documentation reflecting the latest system state. No historical versions.

**How it works**:
- Documentation lives in `docs/` in main branch
- Updates are made directly as code evolves
- Users always see latest documentation
- Breaking changes documented in CHANGELOG.md

**Advantages**:
- Extremely simple (no versioning overhead)
- Users never confused by multiple versions
- All maintenance effort goes to current docs
- Faster iteration (no need to backport doc fixes)
- Lower storage and CI costs

**Disadvantages**:
- No way to reference old behavior
- Users on older deployments see incorrect docs
- Breaking changes can confuse users mid-migration
- Cannot provide version-specific troubleshooting

**Implementation**:
```bash
# Just maintain docs in main branch
git commit -am "docs: Update API reference for new parameters"
git push origin main
```

**Best for**: Rapidly evolving prototypes, internal tools, or projects with always-latest deployment model.

---

### 4. Hybrid: Latest + Archived Releases

**What it is**: Combine single-version simplicity with selective archival for major releases.

**How it works**:
- Main documentation always reflects latest (no versioning)
- When major release occurs, freeze a copy in `docs/versions/v1.0.0/`
- Provide manual links to archived versions
- Current docs have banner: "Looking for v1.0.0 docs? [Click here](versions/v1.0.0)"

**Advantages**:
- Simple for day-to-day development (single version)
- Provides reference for users on old versions
- Minimal overhead (archive only on major releases)
- No complex tooling required
- Clear "latest is preferred" signal

**Disadvantages**:
- Archived versions can become outdated (no backports)
- Manual maintenance of archive directory
- No fancy version switcher UI
- Search doesn't distinguish versions
- Links between versions may break

**Implementation**:
```bash
# On major release v1.0.0
cp -r docs/ docs/versions/v1.0.0/
git add docs/versions/v1.0.0/
git commit -m "docs: Archive v1.0.0 documentation"
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin main v1.0.0

# Add banner to current docs
echo "**Note**: Looking for [v1.0.0 docs](versions/v1.0.0)?" > docs/index.md
```

**Best for**: Projects with infrequent major releases, small user base, limited resources for version maintenance.

---

## Comparison Matrix

| Criterion | Mike Plugin | Git Tags | Latest Only | Hybrid Archive |
|-----------|-------------|----------|-------------|----------------|
| Setup Complexity | High | Low | Minimal | Low |
| Maintenance Burden | High | Low | Minimal | Medium |
| Version Discoverability | Excellent | Poor | N/A | Fair |
| User Experience | Excellent | Poor | Good | Fair |
| Storage Overhead | High | Low | Minimal | Medium |
| CI/CD Complexity | High | Medium | Minimal | Medium |
| Backporting Effort | High | Medium | None | None |
| Best for Stage | Mature | Growing | Early | Transitional |

---

## Decision: Hybrid Approach (Latest + Git Tags)

### Rationale

**Why this fits initial needs**:

1. **Current Project Stage**: GraphRAG MCP server is in active development with constitution v1.0.0 just ratified. The system is evolving rapidly, making complex multi-version documentation premature.

2. **Audience Characteristics**: Primary users are developers and technical integrators who can navigate git tags if needed. They don't require polished version switching UX yet.

3. **Resource Constraints**: Small team with limited bandwidth. Multi-version maintenance would divert effort from feature development and current documentation quality.

4. **Deployment Model**: Server is deployed as remote HTTP service (Railway). Users don't control their version—they use whatever is deployed. This reduces need for version-specific docs.

5. **Constitutional Alignment**: Constitution Principle V (Performance by Design - Documented Optimization) emphasizes capturing changes in troubleshooting.md with dates. Git tags extend this practice to entire documentation state.

6. **Precedent**: Project already uses date-stamped optimization entries in troubleshooting.md. Git tags formalize this pattern at release level.

### Implementation

#### Phase 1: Latest-Only with Git Tags (Now - v1.x)

**Documentation Strategy**:
- Main documentation in `docs/` reflects current system state
- Update docs concurrently with code changes
- Validate docs against live system (per SC-007: 95% success rate)
- Use frontmatter `last_updated` dates to track freshness (per data-model.md)

**Versioning Strategy**:
- Tag releases when constitution version changes or major features ship
- Follow semantic versioning aligned with constitution
- Tag format: `v{MAJOR}.{MINOR}.{PATCH}` (e.g., `v1.0.0`)
- GitHub releases include link to documentation at that tag

**User Communication**:
- Add version badge to README: "Documentation for v1.0.0"
- Include version note in docs/index.md:
  ```markdown
  **Current Version**: v1.0.0 (2026-01-06)
  **Looking for older versions?** See [Releases](https://github.com/ArthurSrz/graphRAGmcp/releases)
  ```
- CHANGELOG.md tracks documentation-breaking changes

**Git Tag Workflow**:
```bash
# When constitution version bumps or major feature ships
git tag -a v1.0.0 -m "Release v1.0.0: Initial constitution ratification"
git push origin v1.0.0

# Create GitHub release with documentation snapshot
gh release create v1.0.0 \
  --title "v1.0.0 - Constitution v1.0.0" \
  --notes "Documentation: [View at this version](https://github.com/ArthurSrz/graphRAGmcp/tree/v1.0.0/docs)"
```

**Accessing Historical Docs**:
Users can view documentation at a specific version:
```bash
# Via GitHub web UI
# Navigate to: https://github.com/ArthurSrz/graphRAGmcp/tree/v1.0.0/docs

# Via local checkout
git checkout v1.0.0
mkdocs serve  # View docs at v1.0.0
git checkout main
```

---

#### Phase 2: Transition to Mike (When needed)

**Trigger Conditions** (any 2 of these):
1. Constitution reaches v2.0.0+ (breaking changes requiring parallel docs)
2. User base exceeds 50 active integrators (support burden increases)
3. Long-term support (LTS) release model adopted (need to maintain v1.x and v2.x)
4. Documentation queries dominate support requests (>40% asking "which version?")
5. External contributors request version switcher (community signal)

**Migration Path**:
```bash
# Install mike
pip install mike

# Import existing tags as versions
mike deploy 1.0.0 --push
mike deploy 1.1.0 --push
mike deploy 2.0.0 latest --push --update-aliases

# Set default
mike set-default latest

# Update mkdocs.yml
echo "  version:
    provider: mike" >> mkdocs.yml
```

**Effort Estimate**: 4-8 hours for initial migration, 1-2 hours per release thereafter

---

### How Users Switch Versions (Phase 1)

**Latest Documentation** (primary):
- Navigate to https://github.com/ArthurSrz/graphRAGmcp/docs or deployed docs site
- Always reflects current system state

**Historical Documentation** (fallback):
- GitHub Releases page lists all versions
- Click release tag → Browse code at that version → Navigate to `docs/`
- Or use git locally: `git checkout v1.0.0 && mkdocs serve`

**No Version Switcher** (Phase 1):
- Intentionally absent to signal "use latest unless you have specific reason"
- Reduces maintenance burden
- Encourages users to upgrade

---

### Future Evolution

**When to Add Full Multi-Version Support**:

**Immediate Triggers** (move to Phase 2):
- Breaking API changes requiring parallel v1/v2 documentation
- Enterprise users request LTS documentation for production systems
- Community contributors open PRs for version switcher

**Gradual Indicators** (watch for these):
- Support requests asking "which version is this?" (track in issue labels)
- Documentation maintenance consuming >20% of development time
- Users deploying self-hosted instances on fixed versions
- Constitution amendments require complex migration guides

**Metrics to Track**:
- GitHub release page views (indicates historical doc interest)
- Support ticket tags: "documentation-version-confusion"
- Time spent backporting doc fixes to tags (if >2 hours/month, consider mike)
- User feedback on documentation surveys

**Cost-Benefit Threshold**:
- Benefit: Multi-version support provides value when >30% of users are on non-latest versions
- Cost: Adds ~2 hours/release + potential backport effort
- Decision: When cost of version confusion exceeds maintenance cost, migrate to Phase 2

---

## Implementation Checklist

### Immediate Actions (Phase 1)
- [ ] Add version badge to README.md showing current version
- [ ] Add version notice to docs/index.md with link to releases
- [ ] Create CHANGELOG.md with versioning policy
- [ ] Document tagging procedure in CONTRIBUTING.md
- [ ] Tag current state as v1.0.0 (aligns with constitution v1.0.0)
- [ ] Create GitHub release v1.0.0 with documentation link

### On Each Release
- [ ] Update version badge in README
- [ ] Create git tag: `git tag -a vX.Y.Z -m "Release X.Y.Z"`
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Create GitHub release with documentation link
- [ ] Update CHANGELOG.md with version notes
- [ ] Validate all docs examples (scripts/validate-docs.py)

### Phase 2 Preparation (future)
- [ ] Monitor trigger conditions (track in project README)
- [ ] Evaluate mike plugin when 2 triggers are met
- [ ] Budget 8 hours for migration to mike
- [ ] Plan version support policy (how long to maintain v1.x docs?)

---

## Alignment with Success Criteria

**SC-005**: Documentation remains current with codebase with <2 week lag
- ✅ Single latest version eliminates version lag
- ✅ Git tags preserve historical accuracy when needed

**SC-007**: Code examples execute successfully 95% of the time
- ✅ Validation only against current system (no backport testing)
- ✅ Historical tags preserved for reference but not validated

**SC-006**: Support requests for "how to" decrease by 60%
- ✅ Single source of truth reduces version confusion
- ✅ Clear "use latest" signal in documentation

**SC-009**: Documentation covers all system capabilities
- ✅ Current docs reflect current capabilities (no partial versions)
- ✅ Git tags ensure historical coverage for specific releases

---

## Alternative Rejected

**Full Multi-Version (Mike) Immediately**: Rejected because:
- Premature optimization (no evidence of multi-version user base)
- Maintenance overhead exceeds current team capacity
- Conflicts with rapid iteration goals
- Users primarily on latest deployment anyway (Railway hosted)

**No Versioning at All**: Rejected because:
- Constitution explicitly versioned (v1.0.0)
- Need to preserve documentation state at constitution milestones
- GitHub releases require reference point
- Troubleshooting.md already uses date-based versioning

---

## References

- Constitution v1.0.0 (`.specify/memory/constitution.md`)
- Troubleshooting pattern (`troubleshooting.md`)
- Data model frontmatter dates (`specs/001-system-documentation/data-model.md`)
- Success criteria SC-005, SC-007 (`specs/001-system-documentation/spec.md`)

**External Resources** (concepts, not fetched):
- Mike documentation: https://github.com/jimporter/mike
- Git tagging: https://git-scm.com/book/en/v2/Git-Basics-Tagging
- Semantic versioning: https://semver.org/
- MkDocs versioning patterns: Common practice in Python ecosystem (Requests, FastAPI, Django)

---

## Conclusion

**Decision**: Implement **Latest + Git Tags** (Phase 1) immediately, with clear migration path to **Mike Plugin** (Phase 2) when multi-version support becomes necessary.

**Why**: Balances simplicity (current needs) with scalability (future growth). Aligns with project stage, team capacity, and constitutional versioning. Provides escape hatch (git tags) without premature complexity.

**Next Steps**: Implement Phase 1 checklist items in documentation feature tasks (via `/speckit.tasks`).
