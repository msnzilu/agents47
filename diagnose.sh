#!/bin/bash

echo "=== DOCKER BUILD DIAGNOSTIC TOOL ==="
echo ""

# 1. Test basic internet connectivity
echo "1. Testing Internet Connectivity..."
echo "   Pinging Google DNS (8.8.8.8)..."
if ping -c 3 8.8.8.8 > /dev/null 2>&1; then
    echo "   ✅ Internet connection working"
else
    echo "   ❌ No internet connection"
fi
echo ""

# 2. Test PyPI connectivity
echo "2. Testing PyPI Connectivity..."
echo "   Checking https://pypi.org..."
if curl -I https://pypi.org --connect-timeout 5 > /dev/null 2>&1; then
    echo "   ✅ Can reach PyPI"
else
    echo "   ❌ Cannot reach PyPI"
fi
echo ""

# 3. Test download speed
echo "3. Testing Download Speed from PyPI..."
echo "   Downloading a small package (requests)..."
time pip download requests --dest /tmp/pip-test --no-deps 2>&1 | tail -5
rm -rf /tmp/pip-test
echo ""

# 4. Check DNS resolution
echo "4. Testing DNS Resolution..."
if nslookup pypi.org > /dev/null 2>&1; then
    echo "   ✅ DNS working"
    nslookup pypi.org | grep "Address:" | tail -1
else
    echo "   ❌ DNS issues"
fi
echo ""

# 5. Check Docker resources
echo "5. Checking Docker Resources..."
docker info 2>/dev/null | grep -E "CPUs:|Total Memory:|Docker Root Dir:"
echo ""

# 6. Check system resources
echo "6. Checking System Resources..."
echo "   CPU cores: $(nproc)"
echo "   Total RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo "   Available RAM: $(free -h | awk '/^Mem:/ {print $7}')"
echo "   Disk space: $(df -h / | awk 'NR==2 {print $4 " available"}')"
echo ""

# 7. Test Docker build speed
echo "7. Testing Docker Build Speed (simple test)..."
cat > /tmp/Dockerfile.test << 'EOF'
FROM python:3.12-slim
RUN pip install --no-cache-dir requests
EOF

echo "   Building test image with single package..."
time docker build -t test-speed -f /tmp/Dockerfile.test /tmp 2>&1 | grep -E "(Step|Successfully)"
docker rmi test-speed 2>/dev/null
rm /tmp/Dockerfile.test
echo ""

# 8. Check for proxy settings
echo "8. Checking Proxy Settings..."
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ] || [ -n "$http_proxy" ] || [ -n "$https_proxy" ]; then
    echo "   ⚠️  Proxy detected:"
    env | grep -i proxy
else
    echo "   ✅ No proxy configured"
fi
echo ""

# 9. Check Docker network
echo "9. Checking Docker Network..."
docker network ls
echo ""

# 10. Test pip install speed
echo "10. Testing Direct Pip Install Speed..."
echo "    Installing 'click' package directly..."
time pip install --no-cache-dir click 2>&1 | tail -3
pip uninstall -y click > /dev/null 2>&1
echo ""

echo "=== DIAGNOSTIC COMPLETE ==="
echo ""
echo "💡 ANALYSIS:"
echo "   - If PyPI is unreachable: Check firewall/network"
echo "   - If DNS fails: Try adding '8.8.8.8' to /etc/resolv.conf"
echo "   - If download is very slow (<100 KB/s): Network issue"
echo "   - If RAM is low (<2GB available): Docker may be struggling"
echo "   - If test build took >2 minutes: System is very slow"