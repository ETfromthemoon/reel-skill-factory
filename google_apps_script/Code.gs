/**
 * Receives Instagram Reel links sent to a Gmail intake address and stores one
 * plain text file per message in a Google Drive folder. Runs under your account.
 * Set INBOX_ADDRESS, ALLOWED_SENDER and DRIVE_FOLDER_ID in Script Properties.
 */

function install() {
  configuration_();
  const existing = ScriptApp.getProjectTriggers().some(
    trigger => trigger.getHandlerFunction() === 'scanInbox'
  );
  if (!existing) {
    ScriptApp.newTrigger('scanInbox').timeBased().everyMinutes(5).create();
  }
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('LAST_SCAN_MS')) {
    props.setProperty('LAST_SCAN_MS', String(Date.now()));
  }
}

function scanInbox() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const config = configuration_();
    const props = PropertiesService.getScriptProperties();
    const lastScan = Number(props.getProperty('LAST_SCAN_MS'));
    if (!lastScan) throw new Error('Ejecuta install() antes de scanInbox()');
    const folder = DriveApp.getFolderById(config.folderId);
    const overlap = new Date(lastScan - 24 * 60 * 60 * 1000);
    const after = Utilities.formatDate(overlap, 'GMT', 'yyyy/MM/dd');
    const query = `to:${config.inboxAddress} after:${after} -in:trash -in:spam`;
    const batchSize = 50;
    let offset = 0;
    while (true) {
      const threads = GmailApp.search(query, offset, batchSize);
      for (const thread of threads) {
        for (const message of thread.getMessages()) {
          if (message.getDate().getTime() < lastScan - 24 * 60 * 60 * 1000) continue;
          if (!addresses_(message.getTo()).includes(config.inboxAddress)) continue;
          if (!addresses_(message.getFrom()).includes(config.allowedSender)) continue;
          const url = reelUrl_(message.getPlainBody() + '\n' + message.getSubject());
          if (!url) continue;
          const filename = message.getId() + '.txt';
          if (!folder.getFilesByName(filename).hasNext()) {
            folder.createFile(filename, url + '\n');
          }
        }
      }
      offset += threads.length;
      if (threads.length < batchSize) break;
      if (offset >= 1000) throw new Error('Más de 1000 conversaciones pendientes; reduce el período y reintenta');
    }
    props.setProperty('LAST_SCAN_MS', String(Date.now()));
  } finally {
    lock.releaseLock();
  }
}

function configuration_() {
  const props = PropertiesService.getScriptProperties();
  const inboxAddress = (props.getProperty('INBOX_ADDRESS') || '').toLowerCase().trim();
  const allowedSender = (props.getProperty('ALLOWED_SENDER') || '').toLowerCase().trim();
  const folderId = (props.getProperty('DRIVE_FOLDER_ID') || '').trim();
  const email = /^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/;
  if (!email.test(inboxAddress) || !email.test(allowedSender) || !folderId) {
    throw new Error('Configura INBOX_ADDRESS, ALLOWED_SENDER y DRIVE_FOLDER_ID');
  }
  return {inboxAddress, allowedSender, folderId};
}

function addresses_(value) {
  return (value.toLowerCase().match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/g) || []);
}

function reelUrl_(value) {
  const match = value.match(/https:\/\/(?:www\.)?instagram\.com\/reel\/([a-zA-Z0-9_-]+)/);
  return match ? `https://www.instagram.com/reel/${match[1]}/` : '';
}
