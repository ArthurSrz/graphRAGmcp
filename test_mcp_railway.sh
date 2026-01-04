#!/bin/bash
# Test script to call graphRAG MCP server on Railway
# Compares query_all vs surgical approaches

set -e

# Railway URL (update with actual URL)
RAILWAY_URL="${RAILWAY_URL:-https://your-app.railway.app}"

echo "================================================================================"
echo "Testing graphRAG MCP on Railway"
echo "================================================================================"
echo "URL: $RAILWAY_URL"
echo ""

# Test query
QUERY="Quelles sont les principales préoccupations des citoyens sur les transports ?"
MAX_COMMUNES=3

echo "Query: $QUERY"
echo "Max communes: $MAX_COMMUNES"
echo ""

# Test 1: grand_debat_query_all (without text chunks)
echo "================================================================================"
echo "TEST 1: grand_debat_query_all (NO text chunks)"
echo "================================================================================"
echo ""

PAYLOAD_QUERY_ALL=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "grand_debat_query_all",
    "arguments": {
      "query": "$QUERY",
      "mode": "global",
      "max_communes": $MAX_COMMUNES,
      "include_sources": true
    }
  }
}
EOF
)

echo "Calling grand_debat_query_all..."
echo ""

RESULT_QUERY_ALL=$(curl -s -X POST "$RAILWAY_URL/mcp" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD_QUERY_ALL")

echo "Response (first 500 chars):"
echo "$RESULT_QUERY_ALL" | jq -r '.result.content[0].text' | head -c 500
echo "..."
echo ""

# Extract key metrics
echo "Key metrics from query_all:"
echo "$RESULT_QUERY_ALL" | jq -r '.result.content[0].text' | jq -r '
  "- Communes queried: \(.communes_queried // 0)",
  "- Entities: \(.provenance.entities | length)",
  "- Communities: \(.provenance.communities | length)",
  "- Source quotes (chunks): \(.provenance.source_quotes | length)"
'
echo ""

# Save full result
echo "$RESULT_QUERY_ALL" | jq '.' > /tmp/railway_query_all_result.json
echo "Full result saved to: /tmp/railway_query_all_result.json"
echo ""

# Test 2: grand_debat_query_all_surgical (with text chunks)
echo "================================================================================"
echo "TEST 2: grand_debat_query_all_surgical (WITH text chunks)"
echo "================================================================================"
echo ""

PAYLOAD_SURGICAL=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "grand_debat_query_all_surgical",
    "arguments": {
      "query": "$QUERY",
      "max_communes": $MAX_COMMUNES
    }
  }
}
EOF
)

echo "Calling grand_debat_query_all_surgical..."
echo ""

RESULT_SURGICAL=$(curl -s -X POST "$RAILWAY_URL/mcp" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD_SURGICAL")

echo "Response (first 500 chars):"
echo "$RESULT_SURGICAL" | jq -r '.result.content[0].text' | head -c 500
echo "..."
echo ""

# Extract key metrics
echo "Key metrics from surgical:"
echo "$RESULT_SURGICAL" | jq -r '.result.content[0].text' | jq -r '
  "- Communes queried: \(.aggregated_stats.total_communes_queried // 0)",
  "- Total entities: \(.aggregated_stats.total_entities // 0)",
  "- Total chunks: \(.aggregated_stats.total_chunks // 0)",
  "- Total relationships: \(.aggregated_stats.total_relationships // 0)",
  "- Avg chunks per commune: \(.aggregated_stats.avg_chunks_per_commune // 0)"
'
echo ""

# Save full result
echo "$RESULT_SURGICAL" | jq '.' > /tmp/railway_surgical_result.json
echo "Full result saved to: /tmp/railway_surgical_result.json"
echo ""

# Comparison
echo "================================================================================"
echo "COMPARISON"
echo "================================================================================"
echo ""

CHUNKS_QUERY_ALL=$(echo "$RESULT_QUERY_ALL" | jq -r '.result.content[0].text' | jq -r '.provenance.source_quotes | length')
CHUNKS_SURGICAL=$(echo "$RESULT_SURGICAL" | jq -r '.result.content[0].text' | jq -r '.aggregated_stats.total_chunks // 0')

echo "| Metric              | query_all     | surgical      |"
echo "|---------------------|---------------|---------------|"
echo "| Text chunks         | $CHUNKS_QUERY_ALL             | $CHUNKS_SURGICAL            |"
echo ""

if [ "$CHUNKS_QUERY_ALL" -eq 0 ] && [ "$CHUNKS_SURGICAL" -gt 0 ]; then
    echo "✅ CONFIRMED: surgical retrieves text chunks, query_all does not!"
    echo ""
    echo "This proves that the issue is not max_tokens, but the absence of"
    echo "text chunk retrieval in query_all."
else
    echo "⚠️  Unexpected results. Please check the full outputs in /tmp/"
fi

echo ""
echo "================================================================================"
echo "Full results saved to:"
echo "  - /tmp/railway_query_all_result.json"
echo "  - /tmp/railway_surgical_result.json"
echo "================================================================================"
