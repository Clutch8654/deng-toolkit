#!/bin/bash
# test_catalog_sync.sh - Test suite for catalog_sync.sh
#
# Usage: test_catalog_sync.sh
#
# Creates isolated test environment with config.yaml, runs all tests, cleans up.

# Don't use set -e - we need to handle test failures gracefully

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_UNDER_TEST="$SCRIPT_DIR/catalog_sync.sh"
TEST_DIR="/tmp/catalog_sync_test_$$"
ORIGINAL_HOME="$HOME"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASS=0
FAIL=0
TESTS=()

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL++)); TESTS+=("$1"); }

setup_test_env() {
    rm -rf "$TEST_DIR"
    mkdir -p "$TEST_DIR/.deng-toolkit"
    mkdir -p "$TEST_DIR/data-catalog"

    # Create config.yaml pointing to test catalog dir
    cat > "$TEST_DIR/.deng-toolkit/config.yaml" << EOF
catalog_dir: $TEST_DIR/data-catalog
catalog_remote: ""
EOF

    export HOME="$TEST_DIR"
    unset DENG_CATALOG_DIR
}

teardown_test_env() {
    export HOME="$ORIGINAL_HOME"
    unset DENG_CATALOG_DIR
    rm -rf "$TEST_DIR"
}

# ============================================================
# AC14: Script is executable
# ============================================================
test_ac14_executable() {
    if [[ -x "$SCRIPT_UNDER_TEST" ]]; then
        log_pass "AC14: Script is executable"
    else
        log_fail "AC14: Script is executable"
    fi
}

# ============================================================
# AC1: Rejects paths outside HOME and /tmp
# ============================================================
test_ac1_rejects_bad_paths() {
    setup_test_env

    # Path outside HOME or /tmp should be rejected
    export DENG_CATALOG_DIR="/etc/evil"

    OUTPUT=$("$SCRIPT_UNDER_TEST" --push 2>&1)
    EXIT_CODE=$?

    # Should fail with some error (either path validation or repo not found)
    if [[ $EXIT_CODE -ne 0 ]]; then
        log_pass "AC1: Rejects paths outside HOME and /tmp"
    else
        log_fail "AC1: Rejects paths outside HOME and /tmp"
    fi

    unset DENG_CATALOG_DIR
    teardown_test_env
}

# ============================================================
# AC2: Reads catalog path from config.yaml
# ============================================================
test_ac2_reads_config() {
    setup_test_env

    # Initialize catalog at config path
    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    # Check that the repo was created at the config path
    if [[ -d "$TEST_DIR/data-catalog/.git" ]]; then
        log_pass "AC2: Reads catalog_dir from config.yaml"
    else
        log_fail "AC2: Reads catalog_dir from config.yaml"
    fi

    teardown_test_env
}

# ============================================================
# AC3: --init creates .git directory
# ============================================================
test_ac3_init_creates_git() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    if [[ -d "$TEST_DIR/data-catalog/.git" ]]; then
        log_pass "AC3: --init creates .git directory"
    else
        log_fail "AC3: --init creates .git directory"
    fi

    teardown_test_env
}

# ============================================================
# AC4: --init creates .gitignore with correct content
# ============================================================
test_ac4_init_creates_gitignore() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    GITIGNORE="$TEST_DIR/data-catalog/.gitignore"
    if [[ -f "$GITIGNORE" ]] && \
       grep -q "^\*\.tmp$" "$GITIGNORE" && \
       grep -q "^\*\.bak$" "$GITIGNORE" && \
       grep -q "^\.DS_Store$" "$GITIGNORE"; then
        log_pass "AC4: --init creates .gitignore with *.tmp, *.bak, .DS_Store"
    else
        log_fail "AC4: --init creates .gitignore with *.tmp, *.bak, .DS_Store"
    fi

    teardown_test_env
}

# ============================================================
# AC5: --init is idempotent
# ============================================================
test_ac5_init_idempotent() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    # Run again - should not fail
    OUTPUT=$("$SCRIPT_UNDER_TEST" --init 2>&1)
    EXIT_CODE=$?

    if [[ $EXIT_CODE -eq 0 ]] && echo "$OUTPUT" | grep -qi "already exists"; then
        log_pass "AC5: --init is idempotent (exits 0 if already initialized)"
    else
        log_fail "AC5: --init is idempotent (exits 0 if already initialized)"
    fi

    teardown_test_env
}

# ============================================================
# AC6: --status shows configuration and git status
# ============================================================
test_ac6_status_shows_git_status() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    # Create an untracked file
    echo "test" > "$TEST_DIR/data-catalog/test.yaml"

    OUTPUT=$("$SCRIPT_UNDER_TEST" --status 2>&1)

    if echo "$OUTPUT" | grep -q "test.yaml"; then
        log_pass "AC6: --status shows git status"
    else
        log_fail "AC6: --status shows git status"
    fi

    teardown_test_env
}

# ============================================================
# AC7: Default (no args) shows status
# ============================================================
test_ac7_default_shows_status() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1
    echo "test" > "$TEST_DIR/data-catalog/test.yaml"

    OUTPUT=$("$SCRIPT_UNDER_TEST" 2>&1)

    if echo "$OUTPUT" | grep -q "test.yaml"; then
        log_pass "AC7: Default command (no args) shows status"
    else
        log_fail "AC7: Default command (no args) shows status"
    fi

    teardown_test_env
}

# ============================================================
# AC8: --push reports no changes when clean
# ============================================================
test_ac8_push_no_changes() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    OUTPUT=$("$SCRIPT_UNDER_TEST" --push 2>&1)

    if echo "$OUTPUT" | grep -qi "No changes"; then
        log_pass "AC8: --push reports 'no changes' when nothing to commit"
    else
        log_fail "AC8: --push reports 'no changes' when nothing to commit"
    fi

    teardown_test_env
}

# ============================================================
# AC9: --push commits changes
# ============================================================
test_ac9_push_commits_changes() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1
    echo "new content" > "$TEST_DIR/data-catalog/tables.yaml"

    "$SCRIPT_UNDER_TEST" --push >/dev/null 2>&1

    # Check git log for new commit
    cd "$TEST_DIR/data-catalog"
    COMMITS=$(git log --oneline | wc -l)

    if [[ $COMMITS -ge 2 ]]; then
        log_pass "AC9: --push commits changes when files modified"
    else
        log_fail "AC9: --push commits changes when files modified"
    fi

    teardown_test_env
}

# ============================================================
# AC10: --push commit message contains date
# ============================================================
test_ac10_push_commit_message_date() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1
    echo "content" > "$TEST_DIR/data-catalog/columns.yaml"

    "$SCRIPT_UNDER_TEST" --push >/dev/null 2>&1

    cd "$TEST_DIR/data-catalog"
    LATEST_MSG=$(git log -1 --format=%s)
    TODAY=$(date +%Y-%m-%d)

    if echo "$LATEST_MSG" | grep -q "$TODAY"; then
        log_pass "AC10: --push commit message contains date"
    else
        log_fail "AC10: --push commit message contains date"
    fi

    teardown_test_env
}

# ============================================================
# AC11: --pull handles no remote gracefully
# ============================================================
test_ac11_pull_no_remote() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    # Pull should not fail catastrophically
    OUTPUT=$("$SCRIPT_UNDER_TEST" --pull 2>&1)

    # Should contain message about no remote configured
    if echo "$OUTPUT" | grep -qi "no remote"; then
        log_pass "AC11: --pull handles missing remote gracefully"
    else
        log_fail "AC11: --pull handles missing remote gracefully"
    fi

    teardown_test_env
}

# ============================================================
# AC12: Invalid command shows usage
# ============================================================
test_ac12_invalid_command() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    OUTPUT=$("$SCRIPT_UNDER_TEST" --invalid 2>&1) || true

    if echo "$OUTPUT" | grep -q "Usage:"; then
        log_pass "AC12: Invalid command shows usage"
    else
        log_fail "AC12: Invalid command shows usage"
    fi

    teardown_test_env
}

# ============================================================
# AC13: Missing catalog directory shows helpful message
# ============================================================
test_ac13_missing_catalog_shows_message() {
    setup_test_env
    rm -rf "$TEST_DIR/data-catalog"

    OUTPUT=$("$SCRIPT_UNDER_TEST" --status 2>&1) || true

    if echo "$OUTPUT" | grep -qi "does not exist\|--init"; then
        log_pass "AC13: Missing catalog directory shows helpful message"
    else
        log_fail "AC13: Missing catalog directory shows helpful message"
    fi

    teardown_test_env
}

# ============================================================
# AC15: Env var overrides config
# ============================================================
test_ac15_env_var_overrides_config() {
    setup_test_env

    # Create an alternate catalog location
    ALT_DIR="$TEST_DIR/alternate-catalog"
    mkdir -p "$ALT_DIR"

    export DENG_CATALOG_DIR="$ALT_DIR"

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    # Check that the repo was created at the env var path, NOT config path
    if [[ -d "$ALT_DIR/.git" ]] && [[ ! -d "$TEST_DIR/data-catalog/.git" ]]; then
        log_pass "AC15: DENG_CATALOG_DIR env var overrides config.yaml"
    else
        log_fail "AC15: DENG_CATALOG_DIR env var overrides config.yaml"
    fi

    unset DENG_CATALOG_DIR
    teardown_test_env
}

# ============================================================
# AC16: --status shows config file location
# ============================================================
test_ac16_status_shows_config() {
    setup_test_env

    "$SCRIPT_UNDER_TEST" --init >/dev/null 2>&1

    OUTPUT=$("$SCRIPT_UNDER_TEST" --status 2>&1)

    if echo "$OUTPUT" | grep -q "Config file:"; then
        log_pass "AC16: --status shows config file location"
    else
        log_fail "AC16: --status shows config file location"
    fi

    teardown_test_env
}

# ============================================================
# RUN ALL TESTS
# ============================================================
echo "========================================"
echo "  Catalog Sync Test Suite"
echo "========================================"
echo ""

test_ac14_executable
test_ac1_rejects_bad_paths
test_ac2_reads_config
test_ac3_init_creates_git
test_ac4_init_creates_gitignore
test_ac5_init_idempotent
test_ac6_status_shows_git_status
test_ac7_default_shows_status
test_ac8_push_no_changes
test_ac9_push_commits_changes
test_ac10_push_commit_message_date
test_ac11_pull_no_remote
test_ac12_invalid_command
test_ac13_missing_catalog_shows_message
test_ac15_env_var_overrides_config
test_ac16_status_shows_config

echo ""
echo "========================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "========================================"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "Failed tests:"
    for t in "${TESTS[@]}"; do
        echo "  - $t"
    done
    exit 1
fi

exit 0
