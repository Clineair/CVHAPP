/**
 * CVH employee receipt photo uploader.
 *
 * Deploy as a web app from clineair891@gmail.com so files are owned by that
 * account and use its Drive quota. Set Script Properties:
 *   UPLOAD_TOKEN       - shared secret (same value as Streamlit [receipts] upload_token)
 *   RECEIPTS_FOLDER_ID - Drive folder that holds one subfolder per employee
 *
 * Do not put tokens, folder ids, or other secrets in this file.
 * Files are only ever created. This script never deletes or edits a file.
 */

var MAX_BYTES = 15 * 1024 * 1024;
var ALLOWED_TYPES = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/heic": "heic",
  "image/heif": "heif",
  "application/pdf": "pdf"
};

function doPost(e) {
  try {
    var props = PropertiesService.getScriptProperties();
    var expected = props.getProperty("UPLOAD_TOKEN") || "";
    var folderId = props.getProperty("RECEIPTS_FOLDER_ID") || "";
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
    var mimeType = String(body.mimeType || "");
    if (!ALLOWED_TYPES.hasOwnProperty(mimeType)) {
      return jsonOutput({ok: false, error: "unsupported type"});
    }
    var bytes = decodeBytes(body.base64);
    if (!bytes || bytes.length < 8) {
      return jsonOutput({ok: false, error: "invalid file"});
    }
    if (bytes.length > MAX_BYTES) {
      return jsonOutput({ok: false, error: "too large"});
    }
    if (!headerMatches(bytes, mimeType)) {
      return jsonOutput({ok: false, error: "invalid file"});
    }
    var parent = DriveApp.getFolderById(folderId);
    var folder = employeeFolder(parent, safeName(body.employee, "Unknown employee"));
    var filename = safeFilename(body.filename, ALLOWED_TYPES[mimeType]);
    var file = folder.createFile(Utilities.newBlob(bytes, mimeType, filename));
    return jsonOutput({ok: true, fileId: file.getId(), url: file.getUrl()});
  } catch (err) {
    return jsonOutput({ok: false, error: "upload failed"});
  }
}

function employeeFolder(parent, name) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var found = parent.getFoldersByName(name);
    if (found.hasNext()) {
      return found.next();
    }
    return parent.createFolder(name);
  } finally {
    lock.releaseLock();
  }
}

function parseJsonBody(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return null;
    }
    var parsed = JSON.parse(e.postData.contents);
    return (parsed && typeof parsed === "object") ? parsed : null;
  } catch (err) {
    return null;
  }
}

function decodeBytes(base64) {
  if (!base64 || typeof base64 !== "string") {
    return null;
  }
  try {
    return Utilities.base64Decode(base64);
  } catch (err) {
    return null;
  }
}

function b(bytes, i) {
  return bytes[i] & 0xff;
}

function headerMatches(bytes, mimeType) {
  if (mimeType === "application/pdf") {
    return b(bytes, 0) === 0x25 && b(bytes, 1) === 0x50 && b(bytes, 2) === 0x44 && b(bytes, 3) === 0x46;
  }
  if (mimeType === "image/jpeg") {
    return b(bytes, 0) === 0xff && b(bytes, 1) === 0xd8 && b(bytes, 2) === 0xff;
  }
  if (mimeType === "image/png") {
    return b(bytes, 0) === 0x89 && b(bytes, 1) === 0x50 && b(bytes, 2) === 0x4e && b(bytes, 3) === 0x47;
  }
  if (mimeType === "image/webp") {
    return b(bytes, 0) === 0x52 && b(bytes, 1) === 0x49 && b(bytes, 8) === 0x57 && b(bytes, 9) === 0x45;
  }
  // HEIC/HEIF: "ftyp" at offset 4.
  return b(bytes, 4) === 0x66 && b(bytes, 5) === 0x74 && b(bytes, 6) === 0x79 && b(bytes, 7) === 0x70;
}

function safeName(name, fallback) {
  name = String(name || "").replace(/[^A-Za-z0-9 .'-]/g, " ").replace(/\s+/g, " ").trim();
  return name ? name.substring(0, 60) : fallback;
}

function safeFilename(name, ext) {
  name = String(name || "receipt");
  name = name.replace(/[^A-Za-z0-9._-]/g, "-");
  while (name.indexOf("--") !== -1) {
    name = name.replace(/--/g, "-");
  }
  name = name.replace(/^-+|-+$/g, "") || "receipt";
  if (!new RegExp("\\." + ext + "$", "i").test(name)) {
    name += "." + ext;
  }
  return name;
}

function tokensEqual(given, expected) {
  given = String(given || "");
  expected = String(expected || "");
  var length = Math.max(given.length, expected.length);
  var diff = given.length ^ expected.length;
  for (var i = 0; i < length; i++) {
    var x = i < given.length ? given.charCodeAt(i) : 0;
    var y = i < expected.length ? expected.charCodeAt(i) : 0;
    diff = diff | (x ^ y);
  }
  return diff === 0;
}

function jsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
