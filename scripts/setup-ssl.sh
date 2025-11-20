#!/bin/bash
# SSL Certificate Setup with Certbot for Infobus

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

setup_ssl() {
    local domain=$(grep "^DOMAIN=" .env.local 2>/dev/null | cut -d= -f2 | tr -d "\"'" | head -1)
    local email=$(grep "^SSL_EMAIL=" .env.local 2>/dev/null | cut -d= -f2 | tr -d "\"'" | head -1)
    
    # Skip SSL setup if no domain configured
    if [ -z "$domain" ] || [ "$domain" = "localhost" ] || [[ "$domain" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${YELLOW}ℹ️  Skipping SSL setup - no valid domain configured${NC}"
        echo "   To enable SSL later, add DOMAIN=your-domain.com to .env.local and run this script again"
        return
    fi
    
    echo -e "${BLUE}🔒 Phase 5: Setting up SSL certificate for ${domain}...${NC}"
    
    # Install certbot if not available
    if ! command -v certbot >/dev/null 2>&1; then
        echo -e "${YELLOW}📦 Installing Certbot...${NC}"
        sudo apt update -qq
        sudo apt install -y certbot python3-certbot-nginx
    fi
    
    # Default email if not provided
    if [ -z "$email" ]; then
        email="admin@${domain}"
        echo -e "${YELLOW}ℹ️  Using default email: ${email}${NC}"
        echo "   You can set SSL_EMAIL=your-email@domain.com in .env.local for custom email"
    fi
    
    # Get nginx container name
    local nginx_container=$(sudo docker ps --format "{{.Names}}" | grep nginx | head -1)
    if [ -z "$nginx_container" ]; then
        echo -e "${RED}❌ nginx container not found${NC}"
        return 1
    fi
    
    # Update nginx config to use specific domain name
    echo -e "${BLUE}🔧 Updating nginx configuration for domain ${domain}...${NC}"
    sed -i "s/server_name _;/server_name ${domain};/" nginx/nginx.conf
    
    # Reload nginx with updated config
    sudo docker restart "$nginx_container"
    sleep 5
    
    # Test domain accessibility
    echo -e "${YELLOW}🌐 Testing domain accessibility...${NC}"
    if ! curl -s -f "http://${domain}/health/" >/dev/null; then
        echo -e "${RED}❌ Domain ${domain} is not accessible. Please check:${NC}"
        echo "   - Domain DNS points to this server IP"
        echo "   - Firewall allows ports 80 and 443"
        echo "   - Domain is correctly configured"
        return 1
    fi
    
    echo -e "${GREEN}✅ Domain is accessible, proceeding with SSL certificate...${NC}"
    
    # Get SSL certificate using certbot
    echo -e "${BLUE}📜 Requesting SSL certificate from Let's Encrypt...${NC}"
    if sudo certbot --nginx \
        --non-interactive \
        --agree-tos \
        --email "$email" \
        --domains "$domain" \
        --redirect; then
        
        echo -e "${GREEN}✅ SSL certificate successfully configured!${NC}"
        
        # Set up auto-renewal
        echo -e "${BLUE}🔄 Setting up automatic certificate renewal...${NC}"
        
        # Add renewal cron job if it doesn't exist
        if ! sudo crontab -l 2>/dev/null | grep -q "certbot renew"; then
            (sudo crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --post-hook 'docker restart $nginx_container'") | sudo crontab -
            echo -e "${GREEN}✅ Auto-renewal scheduled (daily at 12:00)${NC}"
        else
            echo -e "${YELLOW}ℹ️  Auto-renewal already configured${NC}"
        fi
        
        # Test HTTPS
        echo -e "${BLUE}🔍 Testing HTTPS configuration...${NC}"
        if curl -s -f "https://${domain}/health/" >/dev/null; then
            echo -e "${GREEN}🎉 HTTPS is working perfectly!${NC}"
            echo -e "${GREEN}🌐 Your site is now available at: https://${domain}${NC}"
        else
            echo -e "${YELLOW}⚠️  HTTPS certificate installed but testing failed${NC}"
            echo "   This might be a temporary issue. Try accessing https://${domain} manually"
        fi
        
    else
        echo -e "${RED}❌ SSL certificate setup failed${NC}"
        echo "   Common issues:"
        echo "   - Domain not pointing to this server"
        echo "   - Firewall blocking ports 80/443"
        echo "   - Rate limiting (try again later)"
        echo "   - Domain validation failed"
        return 1
    fi
}

# Main execution
echo -e "${BLUE}🔒 Infobus SSL Certificate Setup${NC}"
echo ""

# Check if we have a .env.local with domain
if [ ! -f ".env.local" ]; then
    echo -e "${RED}❌ .env.local file not found${NC}"
    echo "Please create .env.local with DOMAIN=your-domain.com"
    exit 1
fi

if ! grep -q "^DOMAIN=" .env.local; then
    echo -e "${RED}❌ No DOMAIN configured in .env.local${NC}"
    echo "Please add DOMAIN=your-domain.com to .env.local"
    exit 1
fi

# Run SSL setup
setup_ssl

echo ""
echo -e "${GREEN}🔒 SSL setup complete!${NC}"
