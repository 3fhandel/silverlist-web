const SILVER_HOST = "live.silvererp.com";
const DEFAULT_APP_URL = "http://localhost:8000/";

function isSilverCsv(download) {
  if (!download.filename?.toLowerCase().endsWith(".csv")) return false;
  return [download.url, download.finalUrl, download.referrer].some((value) => {
    if (!value) return false;
    try {
      const source = new URL(value);
      if (source.hostname === SILVER_HOST) return true;
      if (source.protocol === "blob:") {
        return new URL(value.slice("blob:".length)).hostname === SILVER_HOST;
      }
    } catch { /* Kein verwertbarer Quell-URL. */ }
    return false;
  });
}

function basename(path) {
  return path.split(/[\\/]/).at(-1);
}

// Chrome blockiert häufig den gesamten Downloads-Ordner für die File System
// Access API. SilverERP-Exporte werden daher in einen unkritischen Unterordner
// gelegt, den der Benutzer separat für SilverLists Web freigeben kann.
chrome.downloads.onDeterminingFilename.addListener((download, suggest) => {
  if (isSilverCsv(download)) {
    suggest({
      filename: `SilverLists Web/${basename(download.filename)}`,
      conflictAction: "uniquify"
    });
  } else {
    suggest();
  }
});

async function getDownload(id) {
  const matches = await chrome.downloads.search({id});
  return matches[0] || null;
}

async function showQuestion(download) {
  const fileName = basename(download.filename);
  const width = 430;
  const height = 255;
  const params = new URLSearchParams({
    download_id: String(download.id),
    filename: fileName
  });
  const [browserWindow, displays] = await Promise.all([
    chrome.windows.getLastFocused().catch(() => null),
    chrome.system.display.getInfo().catch(() => [])
  ]);
  const windowCenter = browserWindow && {
    x: (browserWindow.left || 0) + (browserWindow.width || 0) / 2,
    y: (browserWindow.top || 0) + (browserWindow.height || 0) / 2
  };
  const display = displays.find(({bounds}) => windowCenter &&
    windowCenter.x >= bounds.left && windowCenter.x < bounds.left + bounds.width &&
    windowCenter.y >= bounds.top && windowCenter.y < bounds.top + bounds.height
  ) || displays.find(item => item.isPrimary) || displays[0];
  const position = display ? {
    left: Math.round(display.workArea.left + (display.workArea.width - width) / 2),
    top: Math.round(display.workArea.top + (display.workArea.height - height) / 2)
  } : {};
  await chrome.windows.create({
    url: chrome.runtime.getURL(`download-prompt.html?${params}`),
    type: "popup",
    width,
    height,
    ...position,
    focused: true
  });
}

chrome.downloads.onChanged.addListener(async (change) => {
  if (change.state?.current !== "complete") return;
  const download = await getDownload(change.id);
  if (download && isSilverCsv(download)) await showQuestion(download);
});

chrome.runtime.onMessage.addListener(async (message) => {
  if (message?.type !== "open-download") return;
  const downloadId = Number(message.downloadId);
  const download = await getDownload(downloadId);
  if (!download || !isSilverCsv(download)) return;

  const {silverListsUrl = DEFAULT_APP_URL} = await chrome.storage.sync.get("silverListsUrl");
  const target = new URL(silverListsUrl);
  target.searchParams.set("open_download", basename(download.filename));
  await chrome.tabs.create({url: target.toString()});
});
