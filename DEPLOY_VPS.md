# VPS Deployment Guide (Hostinger/Ubuntu)

Complete guide to deploy Google Maps Lead Scraper on your Hostinger VPS (16GB RAM, 8 cores).

## 📋 Prerequisites

- Hostinger VPS (Ubuntu 20.04/22.04)
- SSH access to your VPS
- Domain name (optional, for HTTPS)
- Root or sudo access

## 🚀 Quick Deployment (Automated)

### Step 1: Connect to Your VPS

```bash
ssh root@your-vps-ip
```

### Step 2: Download and Run Installation Script

```bash
# Download the installation script
curl -o install_vps.sh https://raw.githubusercontent.com/vishnutewary1-bot/ai-google-map-scrapper/main/install_vps.sh

# Make it executable
chmod +x install_vps.sh

# Run it
sudo ./install_vps.sh
```

This will automatically:
- Update system packages
- Install Python 3.11
- Install PostgreSQL
- Install Nginx
- Clone your GitHub repository
- Install all dependencies
- Setup database
- Configure systemd services
- Setup firewall

### Step 3: Configure Environment

```bash
cd /opt/google-maps-scraper
sudo nano .env
```

Update these values:
```env
DB_PASSWORD=your_secure_password
SECRET_KEY=your_secret_key_here
```

### Step 4: Start Services

```bash
sudo systemctl start scraper-api
sudo systemctl start scraper-worker
sudo systemctl enable scraper-api
sudo systemctl enable scraper-worker
```

### Step 5: Access Your Dashboard

Open browser: `http://your-vps-ip:8000`

## 📝 Manual Deployment

If you prefer manual installation:

### 1. Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Python 3.11

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
```

### 3. Install PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 4. Install System Dependencies

```bash
sudo apt install -y git curl wget build-essential libpq-dev nginx
```

### 5. Create Database

```bash
sudo -u postgres psql << EOF
CREATE DATABASE google_maps_scraper;
CREATE USER scraper_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE google_maps_scraper TO scraper_user;
\c google_maps_scraper
GRANT ALL ON SCHEMA public TO scraper_user;
EOF
```

### 6. Clone Repository

```bash
cd /opt
sudo git clone https://github.com/vishnutewary1-bot/ai-google-map-scrapper.git google-maps-scraper
cd google-maps-scraper
```

### 7. Setup Python Environment

```bash
sudo python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
sudo playwright install-deps chromium
```

### 8. Configure Environment

```bash
cp .env.example .env
nano .env
```

Update:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=google_maps_scraper
DB_USER=scraper_user
DB_PASSWORD=your_secure_password

# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Scraper Settings
HEADLESS_MODE=true
MAX_REQUESTS_PER_HOUR=100
```

### 9. Initialize Database

```bash
python main.py init-db
```

### 10. Setup Systemd Services

Create API service:
```bash
sudo nano /etc/systemd/system/scraper-api.service
```

Paste:
```ini
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
```

Create worker service:
```bash
sudo nano /etc/systemd/system/scraper-worker.service
```

Paste:
```ini
[Unit]
Description=Google Maps Scraper Background Worker
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/google-maps-scraper
Environment="PATH=/opt/google-maps-scraper/venv/bin"
ExecStart=/opt/google-maps-scraper/venv/bin/python -m celery -A api.celery_worker worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 11. Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl start scraper-api
sudo systemctl start scraper-worker
sudo systemctl enable scraper-api
sudo systemctl enable scraper-worker
```

### 12. Setup Nginx (Optional - For Domain/SSL)

```bash
sudo nano /etc/nginx/sites-available/scraper
```

Paste:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/scraper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 13. Setup Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

### 14. Setup SSL with Let's Encrypt (Optional)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## ✅ Verify Deployment

### Check Services Status

```bash
sudo systemctl status scraper-api
sudo systemctl status scraper-worker
sudo systemctl status postgresql
sudo systemctl status nginx
```

### View Logs

```bash
# API logs
sudo journalctl -u scraper-api -f

# Worker logs
sudo journalctl -u scraper-worker -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Test API

```bash
curl http://localhost:8000/api/stats
```

### Access Dashboard

- **Direct access**: `http://your-vps-ip:8000`
- **With domain**: `http://your-domain.com`
- **With SSL**: `https://your-domain.com`

## 🔧 Management Commands

### Update Code from GitHub

```bash
cd /opt/google-maps-scraper
sudo git pull origin main
sudo systemctl restart scraper-api
sudo systemctl restart scraper-worker
```

### Run CLI Commands

```bash
cd /opt/google-maps-scraper
source venv/bin/activate

# Scrape
python main.py scrape "pizza in New York" --max-results 100

# Export
python main.py export --format csv --output /tmp/leads.csv

# Stats
python main.py stats
```

### Backup Database

```bash
sudo -u postgres pg_dump google_maps_scraper > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
sudo -u postgres psql google_maps_scraper < backup_20231225.sql
```

## 📊 Monitoring

### Check Resource Usage

```bash
# CPU and Memory
htop

# Disk space
df -h

# Database size
sudo -u postgres psql -c "SELECT pg_size_pretty(pg_database_size('google_maps_scraper'));"
```

### Performance Tuning

Edit PostgreSQL config for 16GB RAM:
```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Recommended settings:
```conf
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10MB
min_wal_size = 1GB
max_wal_size = 4GB
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## 🔒 Security Best Practices

1. **Change default passwords**
   ```bash
   sudo passwd  # Change root password
   sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'new_password';"
   ```

2. **Setup SSH key authentication**
   ```bash
   ssh-copy-id root@your-vps-ip
   ```

3. **Disable password authentication** (after SSH key setup)
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart sshd
   ```

4. **Setup fail2ban**
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   ```

5. **Regular updates**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

## 🐛 Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u scraper-api -n 50

# Check permissions
sudo chown -R www-data:www-data /opt/google-maps-scraper
```

### Database connection error

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
sudo -u postgres psql -c "\l"

# Check credentials in .env
cat /opt/google-maps-scraper/.env
```

### Playwright browser error

```bash
cd /opt/google-maps-scraper
source venv/bin/activate
sudo playwright install-deps chromium
playwright install chromium
```

### Out of memory

```bash
# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 🎯 Next Steps

1. ✅ VPS deployed
2. ✅ Services running
3. ✅ Database configured
4. 🚀 Start scraping via dashboard or CLI
5. 📈 Monitor performance and logs
6. 🔄 Setup automated backups

## 📞 Support

For issues:
- Check logs: `sudo journalctl -u scraper-api -f`
- Verify services: `sudo systemctl status scraper-api`
- Test database: `sudo -u postgres psql google_maps_scraper`
