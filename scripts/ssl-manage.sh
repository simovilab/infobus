#!/bin/bash

# SSL Certificate Management Script for Infobus
set -e

cd "$(dirname "$0")/.."

# Load SSL environment variables
if [ -f ".env.ssl" ]; then
    export $(grep -v '^#' .env.ssl | xargs)
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  init       Initialize SSL certificates (first time setup)"
    echo "  renew      Renew SSL certificates"
    echo "  start-cron Start automatic renewal service"
    echo "  stop-cron  Stop automatic renewal service"
    echo "  status     Check SSL certificate status"
    echo "  logs       Show certbot logs"
    echo "  test       Test with Let's Encrypt staging environment"
    echo ""
}

init_ssl() {
    echo -e "${GREEN}🔒 Initializing SSL certificates for domain: ${SSL_DOMAIN:-infobus.bucr.digital}${NC}"
    
    # Ensure nginx is running first
    if ! docker compose -f docker-compose.production.yml ps nginx | grep -q "Up"; then
        echo -e "${RED}❌ Nginx container must be running first${NC}"
        echo "Please start the production environment:"
        echo "  ./scripts/prod.sh"
        exit 1
    fi
    
    # Run certbot to get initial certificates
    docker compose -f docker-compose.production.yml --profile ssl run --rm certbot
    
    # Reload nginx with new certificates
    echo -e "${YELLOW}🔄 Reloading nginx with new certificates...${NC}"
    docker compose -f docker-compose.production.yml exec nginx nginx -s reload
    
    echo -e "${GREEN}✅ SSL certificates initialized successfully!${NC}"
}

renew_ssl() {
    echo -e "${GREEN}🔄 Renewing SSL certificates...${NC}"
    
    # Run renewal
    docker compose -f docker-compose.production.yml --profile ssl run --rm certbot
    
    # Reload nginx
    echo -e "${YELLOW}🔄 Reloading nginx...${NC}"
    docker compose -f docker-compose.production.yml exec nginx nginx -s reload || echo "Note: nginx reload may be handled automatically"
    
    echo -e "${GREEN}✅ SSL renewal completed!${NC}"
}

start_cron() {
    echo -e "${GREEN}⏰ Starting automatic SSL renewal service...${NC}"
    
    docker compose -f docker-compose.production.yml --profile ssl --profile cron up -d certbot-cron
    
    echo -e "${GREEN}✅ Automatic renewal service started!${NC}"
    echo "Certificates will be checked for renewal twice daily (recommended by Let's Encrypt)"
}

stop_cron() {
    echo -e "${YELLOW}⏰ Stopping automatic SSL renewal service...${NC}"
    
    docker compose -f docker-compose.production.yml stop certbot-cron
    docker compose -f docker-compose.production.yml rm -f certbot-cron
    
    echo -e "${GREEN}✅ Automatic renewal service stopped!${NC}"
}

show_status() {
    echo -e "${GREEN}🔍 SSL Certificate Status${NC}"
    echo ""
    
    # Check if certificates exist
    if docker compose -f docker-compose.production.yml --profile ssl run --rm -T certbot ls /etc/letsencrypt/live/ 2>/dev/null | grep -q "${SSL_DOMAIN:-infobus.bucr.digital}"; then
        echo -e "${GREEN}✅ Certificate exists for ${SSL_DOMAIN:-infobus.bucr.digital}${NC}"
        
        # Show certificate details
        echo ""
        echo "Certificate details:"
        docker compose -f docker-compose.production.yml --profile ssl run --rm -T certbot \
            openssl x509 -in "/etc/letsencrypt/live/${SSL_DOMAIN:-infobus.bucr.digital}/cert.pem" -text -noout | \
            grep -E "(Subject|Issuer|Not After)"
    else
        echo -e "${RED}❌ No certificate found for ${SSL_DOMAIN:-infobus.bucr.digital}${NC}"
    fi
    
    # Check cron service status
    echo ""
    if docker compose -f docker-compose.production.yml ps certbot-cron | grep -q "Up"; then
        echo -e "${GREEN}✅ Automatic renewal service is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Automatic renewal service is not running${NC}"
    fi
}

show_logs() {
    echo -e "${GREEN}📋 Certbot Logs${NC}"
    echo ""
    
    # Show recent logs
    docker compose -f docker-compose.production.yml --profile ssl run --rm -T certbot \
        tail -50 /var/log/letsencrypt/letsencrypt.log 2>/dev/null || echo "No logs found"
}

test_ssl() {
    echo -e "${YELLOW}🧪 Testing SSL setup with Let's Encrypt staging environment${NC}"
    echo "This will use staging certificates (not valid for browsers)"
    
    # Temporarily use staging
    export SSL_STAGING=true
    
    docker compose -f docker-compose.production.yml --profile ssl run --rm \
        -e SSL_STAGING=true certbot
    
    echo -e "${GREEN}✅ Test completed! Check logs for results.${NC}"
}

# Main script logic
case "${1:-}" in
    "init")
        init_ssl
        ;;
    "renew")
        renew_ssl
        ;;
    "start-cron")
        start_cron
        ;;
    "stop-cron")
        stop_cron
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "test")
        test_ssl
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
