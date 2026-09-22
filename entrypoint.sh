#!/bin/bash
set -e

# Default values
CRON_SCHEDULE="${CRON_SCHEDULE:-0 2 * * *}"
RUN_ON_STARTUP="${RUN_ON_STARTUP:-true}"
LOG_FILE="${LOG_FILE:-/app/logs/optibot.log}"

echo "=================================================="
echo "OptiBot Container Starting"
echo "=================================================="
echo "Cron Schedule: $CRON_SCHEDULE"
echo "Run on Startup: $RUN_ON_STARTUP"
echo "Timezone: $TZ"
echo "Log File: $LOG_FILE"
echo "=================================================="

# Create cron job
# Redirect output to log file with timestamps
CRON_JOB="$CRON_SCHEDULE cd /app && echo \"\$(date '+\%Y-\%m-\%d \%H:\%M:\%S') - Cron triggered\" >> $LOG_FILE 2>&1 && /usr/local/bin/python /app/main.py >> $LOG_FILE 2>&1"

# Write cron job to crontab
echo "$CRON_JOB" > /etc/cron.d/optibot

# Set proper permissions
chmod 0644 /etc/cron.d/optibot

# Apply crontab
crontab /etc/cron.d/optibot

echo "✅ Cron job configured: $CRON_SCHEDULE"

# Run on startup if enabled
if [ "$RUN_ON_STARTUP" = "true" ]; then
    echo ""
    echo "Running initial execution..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Initial run on startup" >> $LOG_FILE 2>&1

    # Run main.py but don't exit container if it fails
    set +e  # Temporarily disable exit-on-error
    /usr/local/bin/python /app/main.py >> $LOG_FILE 2>&1
    EXIT_CODE=$?
    set -e  # Re-enable exit-on-error

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Initial execution completed successfully"
    else
        echo "⚠️  Initial execution failed (exit code: $EXIT_CODE)"
        echo "   Check logs: docker exec optibot tail -f $LOG_FILE"
    fi
    echo ""
fi

echo ""
echo "🚀 Starting cron daemon..."
echo "   Logs will be written to: $LOG_FILE"
echo "   To view logs: docker exec <container> tail -f $LOG_FILE"
echo "   To run manually: docker exec <container> python /app/main.py"
echo "=================================================="

# Start cron in foreground
cron -f
