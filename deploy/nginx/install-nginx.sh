#!/bin/bash
# ==============================================================================
# CCC (Connect-Claude Code) Nginx Installer Script
# ==============================================================================
# This script copies the ccc.conf template to the local Nginx configuration
# directory, verifies the configuration syntax, and reloads Nginx.
#
# Features:
#   - Idempotent execution.
#   - Automated Nginx directory detection (macOS Homebrew & Linux standard).
#   - Automatic configuration backup and safe rollback if syntax check fails.
#   - Supports custom environment variables to override paths.
# ==============================================================================

set -euo pipefail

# --- Color formatting ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# --- Check script location ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXAMPLE_CONF="$SCRIPT_DIR/ccc.conf.example"

if [ ! -f "$EXAMPLE_CONF" ]; then
    log_error "Configuration example not found at $EXAMPLE_CONF"
    exit 1
fi

# --- 1. Detect Nginx Config Directory ---
# Priority:
#   1. $NGINX_CONF_DIR environment variable
#   2. /usr/local/etc/nginx (macOS Intel Homebrew)
#   3. /opt/homebrew/etc/nginx (macOS Apple Silicon Homebrew)
#   4. /etc/nginx (Standard Linux)
#   5. Default fallback to /etc/nginx

if [ -n "${NGINX_CONF_DIR:-}" ]; then
    CONF_DIR="$NGINX_CONF_DIR"
    log_info "Using NGINX_CONF_DIR from environment: $CONF_DIR"
else
    if [ -d "/usr/local/etc/nginx" ]; then
        CONF_DIR="/usr/local/etc/nginx"
    elif [ -d "/opt/homebrew/etc/nginx" ]; then
        CONF_DIR="/opt/homebrew/etc/nginx"
    elif [ -d "/etc/nginx" ]; then
        CONF_DIR="/etc/nginx"
    else
        CONF_DIR="/etc/nginx"
        log_warn "No active Nginx directory detected. Defaulting to $CONF_DIR"
    fi
fi

log_info "Detected Nginx configuration directory: $CONF_DIR"

# --- 2. Determine target file path ---
TARGET_FILE=""
LINK_FILE=""
STRUCTURE_TYPE="" # 'servers', 'sites', 'conf.d', 'direct'

if [ -d "$CONF_DIR/servers" ]; then
    # macOS Homebrew style
    TARGET_FILE="$CONF_DIR/servers/ccc.conf"
    STRUCTURE_TYPE="servers"
elif [ -d "$CONF_DIR/sites-available" ] && [ -d "$CONF_DIR/sites-enabled" ]; then
    # Linux Debian/Ubuntu style
    TARGET_FILE="$CONF_DIR/sites-available/ccc.conf"
    LINK_FILE="$CONF_DIR/sites-enabled/ccc.conf"
    STRUCTURE_TYPE="sites"
elif [ -d "$CONF_DIR/conf.d" ]; then
    # RedHat/CentOS / Alpine style
    TARGET_FILE="$CONF_DIR/conf.d/ccc.conf"
    STRUCTURE_TYPE="conf.d"
else
    # Fallback to direct placement in nginx.conf directory
    TARGET_FILE="$CONF_DIR/ccc.conf"
    STRUCTURE_TYPE="direct"
    log_warn "Specific subfolder (servers/sites-available/conf.d) not found. Placing file directly: $TARGET_FILE"
fi

log_info "Nginx target config path: $TARGET_FILE"

# --- Helper: Check Nginx Command ---
NGINX_CMD="nginx"
if ! command -v nginx &>/dev/null; then
    # Try common paths if not in PATH
    if [ -x "/usr/sbin/nginx" ]; then
        NGINX_CMD="/usr/sbin/nginx"
    elif [ -x "/usr/local/bin/nginx" ]; then
        NGINX_CMD="/usr/local/bin/nginx"
    elif [ -x "/opt/homebrew/bin/nginx" ]; then
        NGINX_CMD="/opt/homebrew/bin/nginx"
    else
        log_warn "Nginx command not found on the system. Script will generate config but skip verification and reload."
        NGINX_CMD=""
    fi
fi

# --- 3. Backup and Write Configuration ---
BACKUP_FILE=""
HAS_BACKUP=false

# If ccc.conf already exists, create a backup
if [ -f "$TARGET_FILE" ]; then
    # Only backup if the file actually differs to keep it idempotent and clean
    if cmp -s "$EXAMPLE_CONF" "$TARGET_FILE"; then
        log_info "Target configuration is already identical. No updates needed."
        # We will still proceed to verify and reload just in case
    else
        TIMESTAMP=$(date +%Y%m%d%H%M%S)
        BACKUP_FILE="${TARGET_FILE}.bak.${TIMESTAMP}"
        log_info "Backing up existing configuration to $BACKUP_FILE"

        # Determine if sudo is needed for write/copy
        if [ -w "$TARGET_FILE" ] || [ -w "$(dirname "$TARGET_FILE")" ]; then
            cp "$TARGET_FILE" "$BACKUP_FILE"
        else
            log_warn "Write permissions lacking for Nginx config. Retrying backup with sudo..."
            sudo cp "$TARGET_FILE" "$BACKUP_FILE"
        fi
        HAS_BACKUP=true
    fi
fi

# Write/Copy the new configuration
write_config() {
    log_info "Writing new configuration to $TARGET_FILE"
    if [ -w "$(dirname "$TARGET_FILE")" ]; then
        cp "$EXAMPLE_CONF" "$TARGET_FILE"
    else
        log_warn "Write permissions lacking for Nginx folder. Retrying with sudo..."
        sudo cp "$EXAMPLE_CONF" "$TARGET_FILE"
    fi

    # Handle Linux sites-enabled link if needed
    if [ "$STRUCTURE_TYPE" = "sites" ] && [ -n "$LINK_FILE" ]; then
        if [ ! -L "$LINK_FILE" ] && [ ! -f "$LINK_FILE" ]; then
            log_info "Creating symlink in sites-enabled: $LINK_FILE"
            if [ -w "$(dirname "$LINK_FILE")" ]; then
                ln -sf "$TARGET_FILE" "$LINK_FILE"
            else
                sudo ln -sf "$TARGET_FILE" "$LINK_FILE"
            fi
        fi
    fi
}

write_config

# --- 4. Validate Configuration ---
if [ -n "$NGINX_CMD" ]; then
    log_info "Running Nginx configuration syntax check using '$NGINX_CMD -t'..."

    # Run nginx -t
    TEST_CMD="$NGINX_CMD -t"
    # Check if we need sudo for nginx -t (typically requires root for reading certificates or writing logs)
    if [ "$EUID" -ne 0 ]; then
        TEST_CMD="sudo $NGINX_CMD -t"
    fi

    if eval "$TEST_CMD" 2>/dev/null; then
        log_info "${GREEN}Nginx syntax check passed successfully!${NC}"
    else
        log_error "Nginx syntax check FAILED. Rolling back configuration..."

        # --- Rollback ---
        if [ "$HAS_BACKUP" = "true" ] && [ -f "$BACKUP_FILE" ]; then
            log_info "Restoring previous configuration from $BACKUP_FILE"
            if [ -w "$TARGET_FILE" ]; then
                cp "$BACKUP_FILE" "$TARGET_FILE"
                rm -f "$BACKUP_FILE"
            else
                sudo cp "$BACKUP_FILE" "$TARGET_FILE"
                sudo rm -f "$BACKUP_FILE"
            fi
        else
            log_info "Removing the newly created invalid configuration file."
            if [ -w "$TARGET_FILE" ]; then
                rm -f "$TARGET_FILE"
            else
                sudo rm -f "$TARGET_FILE"
            fi

            # Remove link if Linux site style
            if [ "$STRUCTURE_TYPE" = "sites" ] && [ -n "$LINK_FILE" ]; then
                if [ -L "$LINK_FILE" ]; then
                    if [ -w "$LINK_FILE" ]; then
                        rm -f "$LINK_FILE"
                    else
                        sudo rm -f "$LINK_FILE"
                    fi
                fi
            fi
        fi

        log_error "Rollback complete. Original state restored."
        exit 1
    fi

    # --- 5. Reload Nginx ---
    log_info "Reloading Nginx config..."
    RELOAD_CMD=""
    if command -v systemctl &>/dev/null && systemctl is-active nginx &>/dev/null; then
        RELOAD_CMD="sudo systemctl reload nginx"
    elif [ -n "$NGINX_CMD" ]; then
        if [ "$EUID" -ne 0 ]; then
            RELOAD_CMD="sudo $NGINX_CMD -s reload"
        else
            RELOAD_CMD="$NGINX_CMD -s reload"
        fi
    fi

    if [ -n "$RELOAD_CMD" ]; then
        log_info "Executing reload: $RELOAD_CMD"
        if eval "$RELOAD_CMD"; then
            log_info "${GREEN}Nginx reloaded successfully! 2017 Reverse Proxy is live on Port 80.${NC}"
        else
            log_error "Failed to reload Nginx. Please reload manually."
            exit 1
        fi
    fi
else
    log_warn "Verification and reload skipped as Nginx is not installed/run on this machine."
    log_info "${GREEN}Config file successfully generated at $TARGET_FILE.${NC}"
fi

# --- 6. Print Rollback and Removal Instructions ---
echo -e "\n${BOLD}======================================================================${NC}"
echo -e "${BOLD}CCC Nginx Reverse Proxy Rollback and Removal Guide${NC}"
echo -e "======================================================================"
echo -e "To completely remove the CCC reverse proxy configuration and restore 7788 direct access:"
echo -e "1. Delete the configuration file:"
echo -e "   ${YELLOW}rm -f $TARGET_FILE${NC}"
if [ "$STRUCTURE_TYPE" = "sites" ] && [ -n "$LINK_FILE" ]; then
echo -e "   ${YELLOW}rm -f $LINK_FILE${NC}"
fi
echo -e "2. Test Nginx syntax again:"
echo -e "   ${YELLOW}nginx -t${NC}"
echo -e "3. Reload Nginx to release Port 80:"
echo -e "   ${YELLOW}nginx -s reload${NC} (or sudo systemctl reload nginx)"
echo -e "======================================================================\n"
