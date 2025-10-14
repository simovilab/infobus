# SSL Certificate Management for Infobus (Containerized)

This document describes the containerized SSL certificate management system for Infobus using Docker containers and Let's Encrypt.

## 🏗️ Architecture

The SSL system consists of:

1. **Nginx Container** - Serves the application and ACME challenges
2. **Certbot Container** - Manages SSL certificates
3. **Certbot-Cron Container** - Automatic renewal service
4. **Shared Volumes** - For certificates and webroot challenges

## 📁 Key Files

```
infobus/
├── certbot/
│   └── renew.sh                    # Certificate renewal script
├── nginx/
│   └── nginx.conf                  # Nginx configuration with SSL
├── scripts/
│   └── ssl.sh                      # SSL management script
├── docker-compose.production.yml   # Production configuration with SSL
└── .env.ssl                        # SSL environment variables
```

## 🔧 Quick Commands

```bash
# Check SSL status
./scripts/ssl.sh status

# Manually renew certificates
./scripts/ssl.sh renew

# Start automatic renewal (recommended)
./scripts/ssl.sh start-auto

# Stop automatic renewal
./scripts/ssl.sh stop-auto

# View renewal logs
./scripts/ssl.sh logs

# Test with staging environment
./scripts/ssl.sh test
```

## 🚀 Initial Setup

1. **Start the production environment:**
   ```bash
   ./scripts/prod.sh
   ```

2. **Get initial SSL certificate:**
   ```bash
   sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm \
     -e SSL_DOMAIN=infobus.bucr.digital \
     -e SSL_EMAIL=admin@infobus.bucr.digital \
     --entrypoint="/bin/sh" certbot /usr/local/bin/renew.sh
   ```

3. **Enable automatic renewal:**
   ```bash
   ./scripts/ssl.sh start-auto
   ```

## 🔄 How It Works

### Certificate Acquisition
1. Certbot creates challenge files in `/var/www/certbot/.well-known/acme-challenge/`
2. Nginx serves these files from the shared volume
3. Let's Encrypt validates domain ownership
4. Certificate is stored in shared volume and copied to nginx ssl directory

### Automatic Renewal
- Certbot-cron container runs renewal checks twice daily (recommended by Let's Encrypt)
- Only renews certificates that are within 30 days of expiration
- Automatically reloads nginx when certificates are renewed

## 📊 Volumes

- `letsencrypt_data` - Let's Encrypt certificates and configuration
- `letsencrypt_logs` - Certbot logs
- `certbot_webroot` - ACME challenge files (shared with nginx)
- `ssl_certs` - SSL certificates for nginx

## 🔒 Security Features

- **HTTPS Everywhere** - HTTP automatically redirects to HTTPS
- **HSTS Headers** - Strict-Transport-Security enforced
- **Modern TLS** - Only TLS 1.2 and 1.3 supported
- **Security Headers** - X-Frame-Options, CSP, etc.

## 🛠️ Manual Operations

### Force Certificate Renewal
```bash
sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm \
  -e SSL_DOMAIN=infobus.bucr.digital \
  -e SSL_EMAIL=admin@infobus.bucr.digital \
  --entrypoint="/bin/sh" certbot /usr/local/bin/renew.sh
```

### Check Certificate Expiry
```bash
sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm \
  --entrypoint="openssl" certbot x509 -in /etc/letsencrypt/live/infobus.bucr.digital/cert.pem -noout -dates
```

### View Certbot Logs
```bash
sudo docker compose -f docker-compose.production.yml --profile ssl --profile production run --rm \
  --entrypoint="tail" certbot -f /var/log/letsencrypt/letsencrypt.log
```

## 🚨 Troubleshooting

### ACME Challenge Fails (403/404)
1. Check nginx configuration allows `.well-known/acme-challenge/`
2. Verify certbot webroot volume is mounted correctly
3. Test manually: `curl http://domain/.well-known/acme-challenge/test`

### Certificate Not Loading
1. Check certificates exist in `/etc/nginx/ssl/`
2. Verify nginx configuration syntax: `nginx -t`
3. Ensure certificate files have correct permissions

### Auto-Renewal Not Working
1. Check certbot-cron container is running
2. View cron logs: `docker logs infobus-certbot-cron-1`
3. Test manual renewal first

## ⚙️ Environment Variables

Set these in `.env.ssl`:

- `SSL_DOMAIN` - Domain name (default: infobus.bucr.digital)
- `SSL_EMAIL` - Contact email for Let's Encrypt
- `SSL_STAGING` - Use staging environment for testing (default: false)

## 🔄 Certificate Lifecycle

1. **New Certificate**: Valid for 90 days
2. **Renewal Window**: Attempts renewal 30 days before expiry
3. **Auto-Renewal**: Checks twice daily
4. **Grace Period**: Multiple retry attempts if renewal fails

## 📞 Support

For issues with SSL certificates:
1. Check the troubleshooting section above
2. Review container logs
3. Test with staging environment first
4. Ensure domain DNS is correctly configured

---

**Note**: This system replaces the previous host-based certbot installation with a fully containerized solution for better maintainability and deployment consistency.
