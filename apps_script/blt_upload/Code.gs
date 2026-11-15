/**
 * Bulletins Live Two bulletin PDF uploader.
 *
 * Deploy as a web app from clineair891@gmail.com so created files are owned
 * by that account and use its Drive quota. Set Script Properties:
 *   UPLOAD_TOKEN  - shared secret (same value as Streamlit [blt_checks] upload_token)
 *   FOLDER_ID     - destination Drive folder id
 *
 * Do not put tokens, folder ids, or other secrets in this file.
 */

var MAX_PDF_BYTES = 15 * 1024 * 1024;

function doPost(e) {
  try {
    var expected = PropertiesService.getScriptProperties().getProperty("UPLOAD_TOKEN") || "";
    var folderId = PropertiesService.getScriptProperties().getProperty("FOLDER_ID") || "";
    if (!expected || !folderId) {
      return jsonOutput({ok: false, error: "not configured"});
    }
    var body = parseJsonBody(e);
    if (!body) {
      return jsonOutput({ok: false, error: "invalid request"});
    }
    if (!tokensEqual(body.token, expected)) {
      return jsonOutput({ok: false, error: "unauthorized"});
    }
    var filename = safeFilename(body.filename);
    var bytes = decodePdfBytes(body.base64);
    if (!bytes) {
      return jsonOutput({ok: false, error: "invalid pdf"});
    }
    if (bytes.length > MAX_PDF_BYTES) {
      return jsonOutput({ok: false, error: "too large"});
    }
    if (!isPdfHeader(bytes)) {
      return jsonOutput({ok: false, error: "invalid pdf"});
    }
    var folder = DriveApp.getFolderById(folderId);
    var blob = Utilities.newBlob(bytes, "application/pdf", filename);
    var file = folder.createFile(blob);
    return jsonOutput({
      ok: true,
      fileId: file.getId(),
      url: file.getUrl()
    });
  } catch (err) {
    return jsonOutput({ok: false, error: "upload failed"});
  }
}

function parseJsonBody(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return null;
    }
    var parsed = JSON.parse(e.postData.contents);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return parsed;
  } catch (err) {
    return null;
  }
}

function decodePdfBytes(base64) {
  if (!base64 || typeof base64 !== "string") {
    return null;
  }
  try {
    return Utilities.base64Decode(base64);
  } catch (err) {
    return null;
  }
}

function isPdfHeader(bytes) {
  return bytes &&
    bytes.length >= 4 &&
    bytes[0] === 0x25 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x44 &&
    bytes[3] === 0x46;
}

function safeFilename(name) {
  name = String(name || "bulletin.pdf");
  name = name.replace(/[^A-Za-z0-9._-]/g, "-");
  while (name.indexOf("--") !== -1) {
    name = name.replace(/--/g, "-");
  }
  name = name.replace(/^-+|-+$/g, "");
  if (!name) {
    name = "bulletin.pdf";
  }
  if (!/\.pdf$/i.test(name)) {
    name += ".pdf";
  }
  return name;
}

/**
 * Constant-time-ish comparison so token length or a matching prefix
 * is not leaked by an early return.
 */
function tokensEqual(given, expected) {
  given = String(given || "");
  expected = String(expected || "");
  var length = Math.max(given.length, expected.length);
  var diff = given.length ^ expected.length;
  var i;
  for (i = 0; i < length; i++) {
    var a = i < given.length ? given.charCodeAt(i) : 0;
    var b = i < expected.length ? expected.charCodeAt(i) : 0;
    diff = diff | (a ^ b);
  }
  return diff === 0;
}

function jsonOutput(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
