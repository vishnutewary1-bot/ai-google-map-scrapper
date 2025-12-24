#!/bin/bash

set -e  # Exit on error

echo "========================================"
echo "Google Maps Scraper - VPS Installation"
echo "========================================"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root (use sudo)"
   exit 1
fi

echo "Step 1: Updating system packages..."
echo "----------------------------------------"
apt update && apt upgrade -y

echo ""
echo "Step 2: Installing system dependencies..."
echo "----------------------------------------"
apt install -y software-properties-common git curl wget build-essential libpq-dev nginx

echo ""
echo "Step 3: Installing Python 3.11..."
echo "----------------------------------------"
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

echo ""
echo "Step 4: Installing PostgreSQL..."
echo "----------------------------------------"
apt install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql

echo ""
echo "Step 5: Setting up database..."
echo "----------------------------------------"
# Generate random password
DB_PASSWORD=$(openssl rand -base64 32)

sudo -u postgres psql << EOF
CREATE DATABASE google_maps_scraper;
CREATE USER scraper_user WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE google_maps_scraper TO scraper_user;
\c google_maps_scraper
GRANT ALL ON SCHEMA public TO scraper_user;
EOF

echo "✓ Database created"
echo "  Database: google_maps_scraper"
echo "  User: scraper_user"
echo "  Password: $DB_PASSWORD"
echo ""
echo "IMPORTANT: Save this password! You'll need it for .env configuration"
echo ""

echo "Step 6: Cloning repository..."
echo "----------------------------------------"
cd /opt
if [ -d "google-maps-scraper" ]; then
    echo "Directory exists, pulling latest changes..."
    cd google-maps-scraper
    git pull origin main
else
    git clone https://github.com/vishnutewary1-bot/ai-google-map-scrapper.git google-maps-scraper
    cd google-maps-scraper
fi

echo ""
echo "Step 7: Setting up Python virtual environment..."
echo "----------------------------------------"
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 8: Installing Playwright browsers..."
echo "----------------------------------------"
playwright install chromium
playwright install-deps chromium

echo ""
echo "Step 9: Configuring environment..."
echo "----------------------------------------"
if [ -f .env ]; then
    echo "WARNING: .env file already exists, creating .env.new"
    cp .env.example .env.new
    ENV_FILE=".env.new"
else
    cp .env.example .env
    ENV_FILE=".env"
fi

# Update .env with database credentials
sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$DB_PASSWORD/" $ENV_FILE
sed -i "s/DB_USER=.*/DB_USER=scraper_user/" $ENV_FILE
sed -i "s/DB_NAME=.*/DB_NAME=google_maps_scraper/" $ENV_FILE
sed -i "s/HEADLESS_MODE=.*/HEADLESS_MODE=true/" $ENV_FILE

echo "✓ Environment configured in $ENV_FILE"

echo ""
echo "Step 10: Initializing database tables..."
echo "----------------------------------------"
python main.py init-db

echo ""
echo "Step 11: Setting up systemd services..."
echo "----------------------------------------"

# Create API service
cat > /etc/systemd/system/scraper-api.service << 'EOF'
[Unit]
Description=Google Maps Scraper API
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/google-maps-scraper
Environment="PATH=/opt/google-maps-scraper/venv/bin"
ExecStart=/opt/google-maps-scraper/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✓ API service created"

# Set permissions
chown -R www-data:www-data /opt/google-maps-scraper

# Reload systemd
systemctl daemon-reload

echo ""
echo "Step 12: Configuring firewall..."
echo "----------------------------------------"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
echo "y" | ufw enable

echo ""
echo "Step 13: Starting services..."
echo "----------------------------------------"
systemctl start scraper-api
systemctl enable scraper-api

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Database Credentials:"
echo "  Database: google_maps_scraper"
echo "  User: scraper_user"
echo "  Password: $DB_PASSWORD"
echo ""
echo "Service Status:"
systemctl status scraper-api --no-pager | head -n 10
echo ""
echo "Access your dashboard at:"
echo "  http://$(curl -s ifconfig.me):8000"
echo ""
echo "Next Steps:"
echo "1. Review and update /opt/google-maps-scraper/.env if needed"
echo "2. Check logs: sudo journalctl -u scraper-api -f"
echo "3. Start scraping via dashboard or CLI"
echo ""
echo "CLI Usage:"
echo "  cd /opt/google-maps-scraper"
echo "  source venv/bin/activate"
echo "  python main.py scrape 'pizza in New York' --max-results 50"
echo ""
echo "Deployment guide: /opt/google-maps-scraper/DEPLOY_VPS.md"
echo ""
