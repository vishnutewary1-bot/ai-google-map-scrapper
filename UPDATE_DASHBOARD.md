# Update Dashboard on VPS

Quick guide to update your VPS with the new professional dashboard.

## 🚀 Update Steps (On Your VPS)

### 1. SSH into your VPS

```bash
ssh root@82.29.164.155
```

### 2. Navigate to project directory

```bash
cd /opt/google-maps-scraper
```

### 3. Pull latest changes from GitHub

```bash
git pull origin main
```

### 4. Restart the API service

```bash
sudo systemctl restart scraper-api
```

### 5. Check service status

```bash
sudo systemctl status scraper-api
```

### 6. Access the new dashboard

Open your browser to:

**http://82.29.164.155:8000/dashboard**

(Note the `/dashboard` path - this is the new professional interface)

## 📊 What's New

### Professional Dashboard Features:

✅ **8 Navigation Pages**
- Dashboard Overview with live stats
- New Scrape Job interface
- Jobs Management with DataTables
- Leads Database with advanced filtering
- Bulk Scraping for multiple locations
- Export Data with multiple formats
- Analytics with charts
- Settings & Configuration

✅ **Real-Time Updates**
- Live WebSocket connection
- Auto-refreshing statistics
- Job progress tracking
- Toast notifications

✅ **Data Management**
- Advanced search and filtering
- Sortable columns
- Select multiple leads
- Delete operations
- Export with filters

✅ **Analytics**
- Top categories chart
- Quality distribution
- Activity timeline
- Visual insights

✅ **Bulk Operations**
- Scrape multiple locations at once
- Configurable delays
- Email extraction
- Batch job creation

## 🔍 Troubleshooting

### If dashboard doesn't load:

1. **Check service is running:**
   ```bash
   sudo systemctl status scraper-api
   ```

2. **View logs:**
   ```bash
   sudo journalctl -u scraper-api -f
   ```

3. **Restart service:**
   ```bash
   sudo systemctl restart scraper-api
   ```

### If static files don't load:

```bash
cd /opt/google-maps-scraper
ls -la frontend/
```

Make sure `dashboard.html` and `app.js` exist.

### If WebSocket doesn't connect:

Check firewall allows WebSocket connections:
```bash
sudo ufw status
```

Ensure port 8000 is open.

## 📱 Access Points

- **Old Dashboard:** http://82.29.164.155:8000/
- **New Professional Dashboard:** http://82.29.164.155:8000/dashboard
- **API Docs:** http://82.29.164.155:8000/docs
- **WebSocket:** ws://82.29.164.155:8000/ws

## 🎯 Quick Test

After updating, test these features:

1. ✅ Open dashboard and see live stats
2. ✅ Create a small scrape job (5 results)
3. ✅ Watch real-time progress updates
4. ✅ View scraped leads in database
5. ✅ Test filtering and search
6. ✅ Try exporting to CSV
7. ✅ Check analytics charts

## 💡 Pro Tips

1. **Bookmark the new dashboard:** `/dashboard` has all features
2. **Use filters:** Find exact leads you need faster
3. **Bulk scraping:** Run multiple locations in one go
4. **Export with filters:** Get only relevant data
5. **Check analytics:** Understand your data better

## 🔄 Regular Updates

To keep getting latest features:

```bash
cd /opt/google-maps-scraper
git pull origin main
sudo systemctl restart scraper-api
```

That's it! Your dashboard is now fully professional and feature-rich. 🎉
