```

docker exec -d 42f3acbe6d70 pg_dump -U verboheit_staging -d vmlc_staging -Fc -b -v > backup_20251106.dump
│      │     │ │            │        │                    │               ││  │  │   │
│      │     │ │            │        │                    │               ││  │  │   └─ Output file.
│      │     │ │            │        │                    │               ││  │  └───── Specifies verbose mode.
│      │     │ │            │        │                    │               ││  └──────── Include large objects in the dump.
│      │     │ │            │        │                    │               │└─────────── Out put a custom-format archive suitable for input into pg_restore
│      │     │ │            │        │                    │               └──────────── Selects the format of the output.
│      │     │ │            │        │                    └──────────────────────────── Specifies the name of the database to connect to. 
│      │     │ │            │        └───────────────────────────────────────────────── User name to connect as.
│      │     │ │            └────────────────────────────────────────────────────────── Export a PostgreSQL database as an SQL script or to other formats
│      │     │ └─────────────────────────────────────────────────────────────────────── Container ID 
│      │     └───────────────────────────────────────────────────────────────────────── Detached mode: run command in the background
└──────└─────────────────────────────────────────────────────────────────────────────── Execute a command in a running container
```


## Installing AWS CLI

Here's how to install AWS CLI v2 on different operating systems:

## On Linux (Ubuntu/Debian)

**Quick Installation (all-in-one):**
```bash
# Download AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

# Unzip the installer
unzip awscliv2.zip

# Run the installer
sudo ./aws/install

# Verify installation
aws --version
```

**Step-by-step explanation:**

1. **Install dependencies** (if you don't have them):
```bash
sudo apt update
sudo apt install curl unzip -y
```

2. **Download the AWS CLI v2 installer:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
```
   - `curl` downloads the file from AWS
   - `-o "awscliv2.zip"` saves it with this filename

3. **Unzip the downloaded file:**
```bash
unzip awscliv2.zip
```
   - Extracts the installation files

4. **Run the installation script:**
```bash
sudo ./aws/install
```
   - Installs AWS CLI to `/usr/local/aws-cli/`
   - Creates a symbolic link at `/usr/local/bin/aws`
   - `sudo` is needed because it installs to system directories

5. **Verify the installation:**
```bash
aws --version
```
   - Should show something like: `aws-cli/2.x.x Python/3.x.x Linux/x.x.x`

6. **Clean up installation files (optional):**
```bash
rm -rf awscliv2.zip aws
```

## On macOS

**Using the GUI installer:**
1. Download the `.pkg` file from: https://awscli.amazonaws.com/AWSCLIV2.pkg
2. Double-click and follow the installation wizard

**Using command line:**
```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

## On Windows

1. Download the MSI installer from: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Run the downloaded installer
3. Follow the on-screen instructions

**Or use command line (PowerShell):**
```powershell
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

## In a Docker Container (For Your Backend Work)

Since you're working with Docker, here's how to add AWS CLI to a Dockerfile:

```dockerfile
FROM python:3.9-slim

# Install AWS CLI v2
RUN apt-get update && \
    apt-get install -y curl unzip && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws && \
    apt-get clean

# Verify installation
RUN aws --version

# Your application code
COPY . /app
WORKDIR /app

CMD ["python", "your_script.py"]
```

**How this Dockerfile works:**

1. **apt-get update** - Updates the package list
2. **apt-get install -y curl unzip** - Installs required tools
3. **curl** - Downloads AWS CLI installer
4. **unzip** - Extracts the installer
5. **./aws/install** - Runs the installation
6. **rm -rf** - Cleans up installation files to keep image size small
7. **apt-get clean** - Removes package cache

**Or use the official AWS CLI Docker image:**
```bash
docker pull amazon/aws-cli:latest
```

Then run commands directly:
```bash
docker run --rm -it amazon/aws-cli s3 ls
```

## After Installation: Configure AWS CLI

Once installed, you'll need to configure it with your credentials:

```bash
aws configure
```

You'll be prompted for:
- AWS Access Key ID
- AWS Secret Access Key  
- Default region name (e.g., `us-east-1`)
- Default output format (e.g., `json`)

**Or set environment variables (better for Docker):**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

## Verify Everything Works

Test your installation and configuration:
```bash
# Check version
aws --version

# List S3 buckets (requires valid credentials)
aws s3 ls

# Get current identity (shows which AWS account you're using)
aws sts get-caller-identity
```

The installation is straightforward - just download, unzip, and install! Let me know if you run into any issues.