Here's a comprehensive guide on how to install the Firecrawl server, set up Ngrok, and scrape a website:

1. Install Firecrawl Server

First, we'll create a bash script to automate the Firecrawl installation process:



```bash
#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Update system and install dependencies
sudo apt update
sudo apt install -y curl git nodejs npm redis-server

# Install pnpm
sudo npm install -g pnpm

# Remove existing Firecrawl directory if it exists
if [ -d "firecrawl" ]; then
  echo "Removing existing firecrawl directory..."
  rm -rf firecrawl
fi

# Clone Firecrawl repository
git clone https://github.com/mendableai/firecrawl.git
cd firecrawl

# Verify the presence of package.json
if [ ! -f apps/api/package.json ]; then
  echo "Error: package.json not found in $(pwd)/apps/api"
  exit 1
fi

# Install project dependencies
cd apps/api
pnpm install

# Create .env file
cat << EOF > .env
NUM_WORKERS_PER_QUEUE=8
PORT=3002
HOST=0.0.0.0
REDIS_URL=redis://localhost:6379
REDIS_RATE_LIMIT_URL=redis://localhost:6379
USE_DB_AUTHENTICATION=false
EOF

# Start Redis server
sudo service redis-server start

# Create a systemd service file for Firecrawl workers
sudo tee /etc/systemd/system/firecrawl-workers.service > /dev/null << EOF
[Unit]
Description=Firecrawl Workers
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$(which pnpm) run workers
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Create a systemd service file for Firecrawl main server
sudo tee /etc/systemd/system/firecrawl-server.service > /dev/null << EOF
[Unit]
Description=Firecrawl Main Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$(which pnpm) run start
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start the services
sudo systemctl daemon-reload
sudo systemctl enable firecrawl-workers firecrawl-server
sudo systemctl start firecrawl-workers firecrawl-server

# Get the machine's IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo "Firecrawl installation complete!"
echo "You can access Firecrawl at http://$IP_ADDRESS:3002"
echo "To test, run: curl http://$IP_ADDRESS:3002/test"
echo "To use the crawl endpoint, run:"
echo "curl -X POST http://$IP_ADDRESS:3002/v0/crawl -H \"Content-Type: application/json\" -d '{\"url\": \"https://mendable.ai\"}'"

```

To use this script:

1. Save it as `install_firecrawl.sh`
2. Make it executable: `chmod +x install_firecrawl.sh`
3. Run it: `./install_firecrawl.sh`

2. Set up Ngrok

Now, let's set up Ngrok to expose your local Firecrawl server to the internet:

a. Install Ngrok:
```bash
wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
unzip ngrok-stable-linux-amd64.zip
sudo mv ngrok /usr/local/bin
```

b. Sign up for a free Ngrok account at https://dashboard.ngrok.com/signup

c. Get your authtoken from the Ngrok dashboard and add it to your configuration:
```bash
ngrok authtoken YOUR_AUTHTOKEN
```

d. Start Ngrok to expose your Firecrawl server:
```bash
ngrok http 3002
```

Note the forwarding URL provided by Ngrok (e.g., https://your-subdomain.ngrok.io).

3. Scrape a Website

Now that Firecrawl is installed and exposed via Ngrok, let's create a script to scrape a website:



```bash
#!/bin/bash

NGROK_URL="https://your-subdomain.ngrok.io"  # Replace with your actual Ngrok URL
TARGET_URL="https://example.com"  # Replace with the website you want to scrape

# Function to submit a crawl job
submit_job() {
  response=$(curl -s -X POST $NGROK_URL/v0/crawl \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$TARGET_URL\"}")
  
  job_id=$(echo $response | jq -r '.jobId')
  
  if [ "$job_id" = "null" ]; then
    echo "Failed to submit crawl job. Response: $response"
    exit 1
  fi
  
  echo $job_id
}

# Function to check job status
check_status() {
  local job_id=$1
  status_response=$(curl -s $NGROK_URL/v0/crawl/status/$job_id)
  status=$(echo $status_response | jq -r '.status')
  
  if [ "$status" = "completed" ]; then
    echo $status_response | jq -r '.result'
    return 0
  elif [ "$status" = "failed" ]; then
    echo "Crawl job failed. Response: $status_response"
    return 1
  else
    echo "Job status: $status"
    return 2
  fi
}

# Main script execution
echo "Submitting crawl job for $TARGET_URL"
job_id=$(submit_job)
echo "Crawl job submitted. Job ID: $job_id"

echo "Polling for job completion..."
while true; do
  check_status $job_id
  result=$?
  if [ $result -eq 0 ]; then
    echo "Crawl job completed."
    break
  elif [ $result -eq 1 ]; then
    echo "Crawl job failed."
    break
  else
    echo "Waiting for job to complete..."
    sleep 5
  fi
done

```

To use this script:

1. Install `jq` for JSON parsing: `sudo apt-get install jq`
2. Save the script as `scrape_website.sh`
3. Make it executable: `chmod +x scrape_website.sh`
4. Replace `https://your-subdomain.ngrok.io` with your actual Ngrok URL
5. Replace `https://example.com` with the website you want to scrape
6. Run the script: `./scrape_website.sh`

This script will submit a crawl job to your Firecrawl server, poll for its completion, and print the scraped content when finished.

Full Step-by-Step Guide:

1. Install Firecrawl:
   - Save the installation script as `install_firecrawl.sh`
   - Make it executable: `chmod +x install_firecrawl.sh`
   - Run it: `./install_firecrawl.sh`

2. Set up Ngrok:
   - Install Ngrok:
     ```bash
     wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
     unzip ngrok-stable-linux-amd64.zip
     sudo mv ngrok /usr/local/bin
     ```
   - Sign up at https://dashboard.ngrok.com/signup
   - Get your authtoken and add it: `ngrok authtoken YOUR_AUTHTOKEN`
   - Start Ngrok: `ngrok http 3002`

3. Scrape a website:
   - Install jq: `sudo apt-get install jq`
   - Save the scraping script as `scrape_website.sh`
   - Make it executable: `chmod +x scrape_website.sh`
   - Edit the script to include your Ngrok URL and target website
   - Run the script: `./scrape_website.sh`

By following these steps, you'll have a fully functional Firecrawl server set up, exposed to the internet via Ngrok, and ready to scrape websites.