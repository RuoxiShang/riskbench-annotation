// -----------------------------------------------------------------------
// RiskBench Dynamic Data Collector (Google Apps Script)
// VERSION 3.0 - The "Pixel" Method (GET & POST)
// -----------------------------------------------------------------------

function doPost(e) {
  return handleRequest(e);
}

function doGet(e) {
  return handleRequest(e);
}

function handleRequest(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000); 
  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": "Server busy"}));
  }

  try {
    var doc = SpreadsheetApp.getActiveSpreadsheet();
    // Always use "All" sheet (create if doesn't exist)
    var sheet = doc.getSheetByName("All");
    if (!sheet) {
      sheet = doc.insertSheet("All");
    }
    
    // PARSE DATA
    var data = {};
    
    // 1. Try GET parameters (e.parameter is populated for both GET and POST url-encoded)
    if (e.parameter && Object.keys(e.parameter).length > 0) {
      data = e.parameter;
    }
    // 2. Try POST body (JSON)
    else if (e.postData && e.postData.contents) {
      try {
        data = JSON.parse(e.postData.contents);
      } catch (err) {
        data = {"error": "Failed to parse JSON", "raw": e.postData.contents};
      }
    }
    
    // Add timestamps
    data.server_timestamp = new Date();

    // HEADER LOGIC
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

    // Return a simple JSON response
    return ContentService.createTextOutput(JSON.stringify({"result": "success", "row": sheet.getLastRow()}))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": e.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
