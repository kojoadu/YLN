# Sheets-Only Mode Configuration

This document explains how to configure the YLN application to use Google Sheets as the primary data storage, disabling SQLite.

## Overview

When enabled, Sheets-Only Mode:
- ✅ Stores all user data directly in Google Sheets
- ✅ Uses minimal in-memory SQLite only for session management
- ✅ Eliminates need for persistent SQLite database files
- ✅ Simplifies deployment and data management
- ✅ Provides real-time data access through Google Sheets

## Configuration

### Step 1: Set Environment Variables

Add these environment variables to enable Sheets-Only mode:

```bash
# Database Mode (set in config.py - already configured)
USE_SQLITE=false
USE_SHEETS_ONLY=true

# Google Sheets Configuration
YLN_SHEETS_ENABLED=true
YLN_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here

# Credentials (choose one method):
# Method 1: JSON string (recommended for cloud deployment)
YLN_SHEETS_CREDENTIALS_JSON='{"type":"service_account","project_id":"...", ...}'

# Method 2: File path (for local development)
YLN_SHEETS_CREDENTIALS_PATH=/path/to/your/credentials.json
```

### Step 2: Prepare Google Sheets

1. **Create a Google Spreadsheet** or use an existing one
2. **Get the Spreadsheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
   ```
3. **Create a Google Cloud Service Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create or select a project
   - Enable Google Sheets API and Google Drive API
   - Create a service account
   - Download the JSON credentials file

4. **Share the spreadsheet** with the service account email address

### Step 3: Test Configuration

Run the configuration check script:
```bash
python check_sheets_config.py
```

This will verify:
- ✅ Database mode is properly set
- ✅ Google Sheets credentials are valid
- ✅ Spreadsheet is accessible
- ✅ Required worksheets can be created

## How It Works

### Data Storage
- **Users**: Stored in 'users' worksheet with columns: id, email, password_hash, role, is_verified, created_at
- **Other entities**: Each entity type gets its own worksheet
- **Sessions**: Stored in minimal in-memory SQLite for security

### Database Operations
- **Create**: Writes directly to Google Sheets
- **Read**: Reads directly from Google Sheets  
- **Update**: Updates specific rows in Google Sheets
- **Delete**: Removes rows from Google Sheets

### Fallback Behavior
- Session management uses in-memory SQLite (secure, temporary)
- Critical operations have error handling and retry logic
- Failed writes are queued for retry (stored in in-memory database)

## Benefits

1. **No File Storage**: Eliminates SQLite database files
2. **Real-time Access**: Data is immediately available in Google Sheets
3. **Easy Backup**: Data is automatically backed up by Google
4. **Collaboration**: Multiple users can view/analyze data in sheets
5. **Simplified Deployment**: No database file management needed

## Limitations

1. **Performance**: Slightly slower than SQLite for complex queries
2. **Rate Limits**: Subject to Google Sheets API rate limits
3. **Network Dependency**: Requires internet connection for data operations
4. **Data Size**: Limited by Google Sheets row/column limits

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify service account credentials
   - Ensure APIs are enabled in Google Cloud Console
   - Check spreadsheet sharing permissions

2. **Permission Errors**  
   - Share spreadsheet with service account email
   - Verify service account has Editor permissions

3. **Rate Limiting**
   - Reduce frequency of operations
   - Implement longer delays between requests

4. **Data Not Appearing**
   - Check spreadsheet ID is correct
   - Verify worksheet names match entity types
   - Run configuration check script

### Getting Help

Run the configuration checker:
```bash
python check_sheets_config.py
```

Check application logs for specific error messages related to Google Sheets operations.

## Security Notes

- Service account credentials should be kept secure
- Use environment variables or secure secret management
- Session tokens remain in secure in-memory storage
- User passwords are hashed before storage in sheets