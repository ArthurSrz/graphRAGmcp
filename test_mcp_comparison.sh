#!/bin/bash
# Test script to compare grand_debat_query_all vs grand_debat_query_all_surgical
# via MCP calls

echo "================================================================================"
echo "TEST: Comparing query_all vs surgical via MCP"
echo "================================================================================"
echo ""

# Test query
QUERY="Quelles sont les principales préoccupations des citoyens sur les transports ?"
MAX_COMMUNES=3

echo "Query: $QUERY"
echo "Max communes: $MAX_COMMUNES"
echo ""

# Ensure the server is running
echo "Note: Make sure the MCP server is running before executing these commands"
echo ""

# Test 1: grand_debat_query_all (limited context, no chunks)
echo "================================================================================"
echo "TEST 1: grand_debat_query_all (NO text chunks)"
echo "================================================================================"
echo ""
echo "Command:"
echo "mcp call grand_debat_query_all '{\"query\": \"$QUERY\", \"mode\": \"global\", \"max_communes\": $MAX_COMMUNES}'"
echo ""
echo "Expected result:"
echo "  - Context: Only entity names and community summaries"
echo "  - No text chunks retrieved"
echo "  - Single LLM call aggregates all communes"
echo "  - Response limited to 8192 tokens"
echo ""

# Test 2: grand_debat_query_all_surgical (full context with chunks)
echo "================================================================================"
echo "TEST 2: grand_debat_query_all_surgical (WITH text chunks)"
echo "================================================================================"
echo ""
echo "Command:"
echo "mcp call grand_debat_query_all_surgical '{\"query\": \"$QUERY\", \"max_communes\": $MAX_COMMUNES}'"
echo ""
echo "Expected result:"
echo "  - Vector search per commune"
echo "  - Text chunks retrieved (real citizen contributions)"
echo "  - Separate LLM call per commune (parallel)"
echo "  - Responses concatenated without compression"
echo "  - Full provenance with chunks"
echo ""

echo "================================================================================"
echo "To run these tests, execute:"
echo "================================================================================"
echo ""
echo "1. Start the MCP server:"
echo "   python server.py"
echo ""
echo "2. In another terminal, run the commands above"
echo ""
echo "3. Compare the results:"
echo "   - Check 'provenance.source_quotes' in surgical (should have chunks)"
echo "   - Compare answer length and detail"
echo "   - Check if citizen contributions are quoted"
echo ""
