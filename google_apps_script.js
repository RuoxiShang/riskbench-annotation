// -----------------------------------------------------------------------
// RiskBench Dynamic Data Collector (Google Apps Script)
// VERSION 3.0 - The "Pixel" Method (GET & POST)
// -----------------------------------------------------------------------

// Optional but strongly recommended:
// Set this to the spreadsheet ID from the intended Google Sheet URL:
// https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
//
// Leaving it blank preserves the historical behavior of writing to the
// spreadsheet this Apps Script project is bound to. That is fragile: if the
// script is copied or deployed from a different sheet, submissions will
// succeed but appear in that other sheet.
var SPREADSHEET_ID = "";

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
    var doc = SPREADSHEET_ID
      ? SpreadsheetApp.openById(SPREADSHEET_ID)
      : SpreadsheetApp.getActiveSpreadsheet();

    if (!doc) {
      throw new Error("No target spreadsheet found. Set SPREADSHEET_ID or bind this script to a Sheet.");
    }

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
    
    // Define preferred order for common fields
    var preferredOrder = [
      "server_timestamp", "timestamp", "task", "ui_version", "session_id", "annotator",
      "sample_id", "row_id", "scenario_id", "axis_to_label", "agent_source",
      "stratum_axis", "stratum_state", "stratum_key",
      "label", "confidence", "confidence_label", "completed",
      "quality_flag", "verdict", 
      "consequence", "probability",
      "harm_type_correct", "risk_mechanism_correct",
      "notes",
      "risk_factor", "domain", "risk_type"
    ];

    // 1. Add missing preferred headers first
    for (var i = 0; i < preferredOrder.length; i++) {
      var key = preferredOrder[i];
      if (data.hasOwnProperty(key)) {
        if (headers.indexOf(key) === -1 && newHeaders.indexOf(key) === -1) {
          newHeaders.push(key);
        }
      }
    }

    // 2. Add any other missing headers
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
    return ContentService.createTextOutput(JSON.stringify({
        "result": "success",
        "row": sheet.getLastRow(),
        "spreadsheet_id": doc.getId(),
        "spreadsheet_name": doc.getName(),
        "sheet_name": sheet.getName()
      }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": e.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
