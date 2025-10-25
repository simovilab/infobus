#!/bin/bash
# Generate realistic API traffic for testing the admin dashboard

BASE_URL="http://localhost:8000"

echo "🚀 Generating API traffic..."
echo ""

# Health checks (should be 200)
echo "📡 Health checks..."
for i in {1..5}; do
    curl -s -o /dev/null -w "Health check $i: %{http_code}\n" $BASE_URL/api/health/
    sleep 0.5
done

# Readiness checks (should be 200 or 503)
echo ""
echo "🔍 Readiness checks..."
for i in {1..3}; do
    curl -s -o /dev/null -w "Ready check $i: %{http_code}\n" $BASE_URL/api/ready/
    sleep 0.5
done

# Search endpoint (public)
echo ""
echo "🔎 Search requests..."
curl -s -o /dev/null -w "Search 'plaza': %{http_code}\n" "$BASE_URL/api/search/?q=plaza"
sleep 0.5
curl -s -o /dev/null -w "Search 'stop': %{http_code}\n" "$BASE_URL/api/search/?q=stop"
sleep 0.5

# Autocomplete (public)
echo ""
echo "💬 Autocomplete requests..."
curl -s -o /dev/null -w "Autocomplete 'plaz': %{http_code}\n" "$BASE_URL/api/autocomplete/?q=plaz"
sleep 0.5

# API documentation (public)
echo ""
echo "📚 Documentation access..."
curl -s -o /dev/null -w "API docs: %{http_code}\n" "$BASE_URL/api/docs/"
sleep 0.5
curl -s -o /dev/null -w "OpenAPI schema: %{http_code}\n" "$BASE_URL/api/docs/schema/"
sleep 0.5

# Try some authenticated endpoints (will get 401)
echo ""
echo "🔒 Authenticated endpoints (expecting 401)..."
curl -s -o /dev/null -w "Stops (no auth): %{http_code}\n" "$BASE_URL/api/stops/"
sleep 0.5
curl -s -o /dev/null -w "Routes (no auth): %{http_code}\n" "$BASE_URL/api/routes/"
sleep 0.5

# Non-existent endpoints (will get 404)
echo ""
echo "❌ Non-existent endpoints (expecting 404)..."
curl -s -o /dev/null -w "Fake endpoint 1: %{http_code}\n" "$BASE_URL/api/nonexistent/"
sleep 0.5
curl -s -o /dev/null -w "Fake endpoint 2: %{http_code}\n" "$BASE_URL/api/fake-data/"
sleep 0.5

# More successful requests
echo ""
echo "✅ More successful requests..."
for i in {1..10}; do
    endpoint=$(( $i % 3 ))
    case $endpoint in
        0) curl -s -o /dev/null -w "Health $i: %{http_code}\n" $BASE_URL/api/health/ ;;
        1) curl -s -o /dev/null -w "Ready $i: %{http_code}\n" $BASE_URL/api/ready/ ;;
        2) curl -s -o /dev/null -w "Search $i: %{http_code}\n" "$BASE_URL/api/search/?q=test$i" ;;
    esac
    sleep 0.3
done

echo ""
echo "✨ Traffic generation complete!"
echo ""
echo "📊 View the dashboard at:"
echo "   http://localhost:8000/admin/api/metrics/"
echo ""
echo "   Login with: admin / admin"
echo ""
