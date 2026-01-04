#!/bin/bash
# Test script to call graphRAG MCP server on Railway with proper session handling
# Compares query_all vs surgical approaches via MCP protocol

set -e

# Railway URL
RAILWAY_URL="https://graphragmcp-production.up.railway.app/mcp"

echo "================================================================================"
echo "Testing graphRAG MCP on Railway (with session management)"
echo "================================================================================"
echo "URL: $RAILWAY_URL"
echo ""

# Test query
QUERY="Quelles sont les principales préoccupations des citoyens sur les transports ?"
MAX_COMMUNES=3

echo "Query: $QUERY"
echo "Max communes: $MAX_COMMUNES"
echo ""

# Step 1: Initialize session
echo "================================================================================"
echo "STEP 1: Initializing MCP session"
echo "================================================================================"
echo ""

INIT_RESPONSE=$(curl -s -i -X POST "$RAILWAY_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    },
    "id": 1
  }')

# Extract session ID from headers
SESSION_ID=$(echo "$INIT_RESPONSE" | grep -i "mcp-session-id:" | awk '{print $2}' | tr -d '\r')

if [ -z "$SESSION_ID" ]; then
    echo "ERROR: Failed to get session ID"
    echo "Response:"
    echo "$INIT_RESPONSE"
    exit 1
fi

echo "✓ Session initialized: $SESSION_ID"
echo ""

# Test 1: grand_debat_query_all (without text chunks)
echo "================================================================================"
echo "TEST 1: grand_debat_query_all (NO text chunks)"
echo "================================================================================"
echo ""

PAYLOAD_QUERY_ALL='{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "grand_debat_query_all",
    "arguments": {
      "query": "'"$QUERY"'",
      "mode": "global",
      "max_communes": '"$MAX_COMMUNES"',
      "include_sources": true
    }
  },
  "id": 2
}'

echo "Calling grand_debat_query_all..."
echo ""

RESULT_QUERY_ALL=$(curl -s -X POST "$RAILWAY_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d "$PAYLOAD_QUERY_ALL")

echo "Response (first 500 chars):"
echo "$RESULT_QUERY_ALL" | head -c 500
echo "..."
echo ""

# Parse result
if echo "$RESULT_QUERY_ALL" | jq -e '.result.content[0].text' > /dev/null 2>&1; then
    ANSWER_TEXT=$(echo "$RESULT_QUERY_ALL" | jq -r '.result.content[0].text')

    echo "Key metrics from query_all:"
    echo "$ANSWER_TEXT" | jq -r '
      "- Communes queried: \(.communes_queried // 0)",
      "- Source quotes (chunks): \(.provenance.source_quotes | length)"
    ' 2>/dev/null || echo "  (Could not parse provenance)"
else
    echo "ERROR: Unexpected response format"
fi
echo ""

# Save result
echo "$RESULT_QUERY_ALL" | jq '.' > /tmp/railway_query_all_result.json 2>/dev/null || echo "$RESULT_QUERY_ALL" > /tmp/railway_query_all_result.json
echo "Full result saved to: /tmp/railway_query_all_result.json"
echo ""

# Test 2: grand_debat_query_all_surgical (with text chunks)
echo "================================================================================"
echo "TEST 2: grand_debat_query_all_surgical (WITH text chunks)"
echo "================================================================================"
echo ""

PAYLOAD_SURGICAL='{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "grand_debat_query_all_surgical",
    "arguments": {
      "query": "'"$QUERY"'",
      "max_communes": '"$MAX_COMMUNES"'
    }
  },
  "id": 3
}'

echo "Calling grand_debat_query_all_surgical..."
echo ""

RESULT_SURGICAL=$(curl -s -X POST "$RAILWAY_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d "$PAYLOAD_SURGICAL")

echo "Response (first 500 chars):"
echo "$RESULT_SURGICAL" | head -c 500
echo "..."
echo ""

# Parse result
if echo "$RESULT_SURGICAL" | jq -e '.result.content[0].text' > /dev/null 2>&1; then
    ANSWER_TEXT=$(echo "$RESULT_SURGICAL" | jq -r '.result.content[0].text')

    echo "Key metrics from surgical:"
    echo "$ANSWER_TEXT" | jq -r '
      "- Communes queried: \(.aggregated_stats.total_communes_queried // 0)",
      "- Total chunks: \(.aggregated_stats.total_chunks // 0)",
      "- Total entities: \(.aggregated_stats.total_entities // 0)",
      "- Avg chunks per commune: \(.aggregated_stats.avg_chunks_per_commune // 0)"
    ' 2>/dev/null || echo "  (Could not parse stats)"
else
    echo "ERROR: Unexpected response format"
fi
echo ""

# Save result
echo "$RESULT_SURGICAL" | jq '.' > /tmp/railway_surgical_result.json 2>/dev/null || echo "$RESULT_SURGICAL" > /tmp/railway_surgical_result.json
echo "Full result saved to: /tmp/railway_surgical_result.json"
echo ""

# Comparison
echo "================================================================================"
echo "COMPARISON"
echo "================================================================================"
echo ""

# Extract chunk counts
CHUNKS_QUERY_ALL=0
CHUNKS_SURGICAL=0

if [ -f /tmp/railway_query_all_result.json ]; then
    CHUNKS_QUERY_ALL=$(jq -r '.result.content[0].text | fromjson | .provenance.source_quotes | length' /tmp/railway_query_all_result.json 2>/dev/null || echo "0")
fi

if [ -f /tmp/railway_surgical_result.json ]; then
    CHUNKS_SURGICAL=$(jq -r '.result.content[0].text | fromjson | .aggregated_stats.total_chunks // 0' /tmp/railway_surgical_result.json 2>/dev/null || echo "0")
fi

echo "| Metric              | query_all     | surgical      |"
echo "|---------------------|---------------|---------------|"
echo "| Text chunks         | $CHUNKS_QUERY_ALL             | $CHUNKS_SURGICAL            |"
echo ""

if [ "$CHUNKS_QUERY_ALL" -eq 0 ] && [ "$CHUNKS_SURGICAL" -gt 0 ]; then
    echo "✅ CONFIRMED: surgical retrieves text chunks, query_all does not!"
    echo ""
    echo "This proves that the issue is NOT max_tokens, but the absence of"
    echo "text chunk retrieval in query_all."
else
    echo "Results:"
    echo "  query_all chunks: $CHUNKS_QUERY_ALL"
    echo "  surgical chunks: $CHUNKS_SURGICAL"
fi

echo ""
echo "================================================================================"
echo "Full results saved to:"
echo "  - /tmp/railway_query_all_result.json"
echo "  - /tmp/railway_surgical_result.json"
echo "================================================================================"
