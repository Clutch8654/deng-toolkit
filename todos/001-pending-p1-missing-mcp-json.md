---
status: completed
priority: p1
issue_id: "001"
tags: [code-review, architecture, plugin-structure]
dependencies: []
completed_date: 2026-01-27
---

# Missing .mcp.json File

## Problem Statement

The plugin manifest at `.claude-plugin/plugin.json` declares an MCP server configuration:

```json
"mcpServers": {
  "file": ".mcp.json"
}
```

However, the `.mcp.json` file does not exist. This will cause plugin initialization failures or warnings when Claude Code attempts to load the plugin.

## Findings

- **Source**: architecture-strategist, pattern-recognition-specialist agents
- **Location**: `.claude-plugin/plugin.json` lines 44-46
- **Impact**: HIGH - Plugin may fail to load or produce errors

## Proposed Solutions

### Option A: Create .mcp.json (Recommended)
**Pros**: Completes the plugin structure, enables MCP tools
**Cons**: Requires MCP server implementation
**Effort**: Small (just the config file) to Large (full MCP server)
**Risk**: Low

Create `.mcp.json` at plugin root:
```json
{
  "mcpServers": {
    "deng-catalog": {
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}/servers/catalog-mcp", "python", "server.py"]
    }
  }
}
```

### Option B: Remove mcpServers from plugin.json
**Pros**: Quick fix, no broken references
**Cons**: Loses planned MCP functionality
**Effort**: Small
**Risk**: Low

Remove lines 44-46 from plugin.json until MCP server is ready.

### Option C: Create empty placeholder .mcp.json
**Pros**: Fixes immediate error, allows incremental development
**Cons**: Empty config may have its own issues
**Effort**: Small
**Risk**: Medium

```json
{
  "mcpServers": {}
}
```

## Recommended Action

Option A - This is Task #1 and #8 in the existing task list. Proceed with creating `.mcp.json` and the MCP server.

## Technical Details

**Affected files:**
- `.claude-plugin/plugin.json`
- `.mcp.json` (to be created)
- `servers/catalog-mcp/` (to be created)

## Acceptance Criteria

- [x] `.mcp.json` file exists at plugin root
- [x] Plugin loads without errors
- [x] MCP tools are discoverable (if Option A)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-27 | Identified in code review | Plugin SDK requires all referenced files to exist |
| 2026-01-27 | Fixed: Created `.mcp.json` and `servers/catalog_mcp/` | TDD approach with 13 passing tests |

## Resources

- Task #1: Create .mcp.json configuration
- Task #8: Create MCP server at servers/catalog-mcp/
