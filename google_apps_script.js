// -----------------------------------------------------------------------
// RiskBench Dynamic Data Collector (Google Apps Script)
// VERSION 2.0 - Robust CORS Handling
// -----------------------------------------------------------------------

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000); 
  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": "Server busy"}));
  }

  try {
    var doc = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = doc.getActiveSheet();
    
    // PARSE DATA: Handle different ways data might arrive
    var data = {};
    try {
      // 1. Try parsing raw body (works for fetch body: JSON.stringify(data))
      if (e.postData && e.postData.contents) {
        data = JSON.parse(e.postData.contents);
      } 
      // 2. Fallback: check if it came as a parameter (sometimes happens with forms)
      else if (e.parameter && Object.keys(e.parameter).length > 0) {
        data = e.parameter;
      }
    } catch (parseError) {
      // If JSON parse fails, maybe it's a key=value string?
      data = {"error": "Failed to parse JSON", "raw": e.postData.contents};
    }
    
    // Add timestamps
    data.server_timestamp = new Date();

    // HEADER LOGIC (Dynamic Columns)
    var lastCol = sheet.getLastColumn();
    var headers = [];
    if (lastCol > 0) {
      headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    }

    var newHeaders = [];
    var keys = Object.keys(data);
    
    for (var k = 0; k < keys.length; k++) {
      var key = keys[k];
      if (headers.indexOf(key) === -1 && newHeaders.indexOf(key) === -1) {
        newHeaders.push(key);
      }
    }
    
    if (newHeaders.length > 0) {
      sheet.getRange(1, headers.length + 1, 1, newHeaders.length).setValues([newHeaders]);
      headers = headers.concat(newHeaders);
    }

    // ROW CONSTRUCTION
    var newRow = [];
    for (var h = 0; h < headers.length; h++) {
      var header = headers[h];
      var value = data[header];
      if (value && typeof value === 'object') {
        value = JSON.stringify(value);
      }
      newRow.push(value !== undefined ? value : "");
    }

    sheet.appendRow(newRow);

    // RETURN SUCCESS
    // Important: Return JSON but with text/plain mime type to satisfy CORS in some browsers
    return ContentService.createTextOutput(JSON.stringify({"result": "success", "row": sheet.getLastRow()}))
      .setMimeType(ContentService.MimeType.TEXT);

  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": e.toString()}))
      .setMimeType(ContentService.MimeType.TEXT);
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  return ContentService.createTextOutput("RiskBench Collector is Online.");
}
