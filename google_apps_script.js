// -----------------------------------------------------------------------
// RiskBench Dynamic Data Collector (Google Apps Script)
// -----------------------------------------------------------------------
//
// INSTRUCTIONS:
// 1. Create a new Google Sheet (sheet.new)
// 2. Go to Extensions > Apps Script
// 3. Paste this entire code there (replacing everything)
// 4. Click "Deploy" > "New Deployment"
// 5. Select Type: "Web App"
// 6. Set "Who has access" to "Anyone" (Crucial!)
// 7. Deploy and copy the Web App URL
// 8. Paste the URL into annotation_ui.html (GOOGLE_SCRIPT_URL variable)

function doPost(e) {
  // 1. robust locking to prevent race conditions from multiple users
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000); // wait up to 30s for other requests to finish
  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": "Server busy"}));
  }

  try {
    var doc = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = doc.getActiveSheet();
    
    // Parse the incoming JSON data
    var data = JSON.parse(e.postData.contents);
    
    // add server-side timestamp
    data.server_timestamp = new Date();

    // 2. DYNAMIC HEADER LOGIC
    // Get existing headers from the first row
    var lastCol = sheet.getLastColumn();
    var headers = [];
    if (lastCol > 0) {
      headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    }

    // Check if we need to add any NEW columns
    var newHeaders = [];
    var keys = Object.keys(data);
    
    for (var k = 0; k < keys.length; k++) {
      var key = keys[k];
      if (headers.indexOf(key) === -1 && newHeaders.indexOf(key) === -1) {
        newHeaders.push(key);
      }
    }
    
    // If new columns found, add them to the header row
    if (newHeaders.length > 0) {
      sheet.getRange(1, headers.length + 1, 1, newHeaders.length).setValues([newHeaders]);
      // Refresh our local list of headers
      headers = headers.concat(newHeaders);
    }

    // 3. CONSTRUCT THE ROW
    // Map the data to the correct column index based on headers
    var newRow = [];
    for (var h = 0; h < headers.length; h++) {
      var header = headers[h];
      var value = data[header];
      
      // Handle arrays/objects by stringifying them
      if (value && typeof value === 'object') {
        value = JSON.stringify(value);
      }
      
      // Default to empty string if data missing for this column
      newRow.push(value !== undefined ? value : "");
    }

    // 4. APPEND TO SHEET
    sheet.appendRow(newRow);

    return ContentService.createTextOutput(JSON.stringify({"result": "success", "row": sheet.getLastRow()}))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": e.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

// Needed for CORS (Cross-Origin) requests to work
function doGet(e) {
  return ContentService.createTextOutput("RiskBench Collector is Online.");
}
