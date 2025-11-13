#!/bin/bash

# Simplified SSL management script for containerized Infobus
set -e

cd "$(dirname "$0")/.."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo -e "${BLUE}🔒 Infobus SSL Management (Containerized)${NC}"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status     Check SSL certificate and service status"
    echo "  renew      Manually renew SSL certificates"
    echo "  start-auto Start automatic renewal service (runs twice daily)"
    echo "  stop-auto  Stop automatic renewal service"
    echo "  logs       Show SSL renewal logs"
    echo "  test       Test certificate with staging environment"
    echo ""
}

check_status() {
    echo -e "${GREEN}🔍 SSL Certificate Status${NC}"
    echo ""
    
    # Check HTTPS access
    if curl -s -I https://infobus.bucr.digital > /dev/null 2>&1; then
        echo -e "${GREEN}✅ HTTPS is working${NC}"
    else
        echo -e "${RED}❌ HTTPS is not working${NC}"
    fi
    
    # Check HTTP redirect
    if curl -s -I http://infobus.bucr.digital | grep -q "301"; then
        echo -e "${GREEN}✅ HTTP redirects to HTTPS${NC}"
    else
        echo -e "${YELLOW}⚠️  HTTP redirect may not be working${NC}"
    fi
    
    # Check certificate expiry
    echo ""
    echo "Certificate details:"
    if sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm --entrypoint="openssl" certbot x509 -in /etc/letsencrypt/live/infobus.bucr.digital/cert.pem -text -noout 2>/dev/null | grep -E "(Subject|Issuer|Not After)"; then
        :
    else
        echo -e "${RED}❌ Could not retrieve certificate details${NC}"
    fi
    
    # Check auto-renewal service
    echo ""
    if sudo docker compose -f docker-compose.production.yml ps certbot-cron | grep -q "Up"; then
        echo -e "${GREEN}✅ Auto-renewal service is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Auto-renewal service is not running${NC}"
        echo "  Run: $0 start-auto"
    fi
}

renew_certificates() {
    echo -e "${GREEN}🔄 Renewing SSL certificates...${NC}"
    
    # Run renewal
    sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm \
        -e SSL_DOMAIN=infobus.bucr.digital \
        -e SSL_EMAIL=admin@infobus.bucr.digital \
        -e SSL_STAGING=false \
        --entrypoint="/bin/sh" certbot /usr/local/bin/renew.sh
    
    # Reload nginx
    echo -e "${YELLOW}🔄 Reloading nginx...${NC}"
    sudo docker compose -f docker-compose.production.yml exec nginx nginx -s reload
    
    echo -e "${GREEN}✅ SSL renewal completed!${NC}"
}

start_auto_renewal() {
    echo -e "${GREEN}⏰ Starting automatic SSL renewal service...${NC}"
    
    sudo docker compose -f docker-compose.production.yml --profile production --profile ssl --profile cron up -d certbot-cron
    
    echo -e "${GREEN}✅ Auto-renewal service started!${NC}"
    echo "Certificates will be checked for renewal twice daily"
}

stop_auto_renewal() {
    echo -e "${YELLOW}⏰ Stopping automatic SSL renewal service...${NC}"
    
    sudo docker compose -f docker-compose.production.yml stop certbot-cron
    sudo docker compose -f docker-compose.production.yml rm -f certbot-cron
    
    echo -e "${GREEN}✅ Auto-renewal service stopped!${NC}"
}

show_logs() {
    echo -e "${GREEN}📋 SSL Renewal Logs${NC}"
    echo ""
    
    if sudo docker compose -f docker-compose.production.yml ps certbot-cron | grep -q "Up"; then
        echo "Recent auto-renewal logs:"
        sudo docker logs infobus-certbot-cron-1 --tail=50
    else
        echo -e "${YELLOW}Auto-renewal service is not running${NC}"
    fi
    
    echo ""
    echo "Last manual renewal logs:"
    sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm -T \
        --entrypoint="tail" certbot -50 /var/log/letsencrypt/letsencrypt.log 2>/dev/null || echo "No logs found"
}

test_staging() {
    echo -e "${YELLOW}🧪 Testing with Let's Encrypt staging environment${NC}"
    echo "This will request a test certificate (not valid for browsers)"
    
    sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm \
        -e SSL_DOMAIN=infobus.bucr.digital \
        -e SSL_EMAIL=admin@infobus.bucr.digital \
        -e SSL_STAGING=true \
        --entrypoint="/bin/sh" certbot /usr/local/bin/renew.sh
    
    echo -e "${GREEN}✅ Staging test completed!${NC}"
}

# Main script logic
case "${1:-}" in
    "status")
        check_status
        ;;
    "renew")
        renew_certificates
        ;;
    "start-auto")
        start_auto_renewal
        ;;
    "stop-auto")
        stop_auto_renewal
        ;;
    "logs")
        show_logs
        ;;
    "test")
        test_staging
        ;;
    *)
        print_usage
        ;;
esac
