// Single-view pages: tabs switch panels, tiles pick what the stage shows, and a #hash opens a given item.
// Without this script every panel and every stage article stays visible and the page reads top to bottom.
(function () {
  document.documentElement.classList.add("js");

  function showTab(tab, focus) {
    var list = tab.closest('[role="tablist"]');
    list.querySelectorAll('[role="tab"]').forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      var p = document.getElementById(t.getAttribute("aria-controls"));
      if (p) p.hidden = !on;
    });
    if (focus) tab.focus();
  }

  function pick(tile, scroll) {
    var board = tile.closest(".board");
    var stage = document.getElementById(board.dataset.stage);
    board.querySelectorAll(".tile").forEach(function (t) { t.setAttribute("aria-pressed", t === tile ? "true" : "false"); });
    stage.querySelectorAll(":scope > article").forEach(function (a) { a.hidden = a.dataset.item !== tile.dataset.item; });
    // on a phone the stage sits under the board, so bring it into view
    if (scroll && window.matchMedia("(max-width: 899.98px), (max-height: 599.98px)").matches) {
      stage.scrollIntoView({ block: "start" });
    }
  }

  document.querySelectorAll('[role="tablist"]').forEach(function (list) {
    var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { showTab(t, false); });
      t.addEventListener("keydown", function (e) {
        var j = null;
        if (e.key === "ArrowRight") j = (i + 1) % tabs.length;
        if (e.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
        if (e.key === "Home") j = 0;
        if (e.key === "End") j = tabs.length - 1;
        if (j !== null) { e.preventDefault(); showTab(tabs[j], true); }
      });
    });
    showTab(tabs.filter(function (t) { return t.getAttribute("aria-selected") === "true"; })[0] || tabs[0], false);
  });

  document.querySelectorAll(".board[data-stage]").forEach(function (board) {
    var tiles = board.querySelectorAll(".tile[data-item]");
    tiles.forEach(function (t) { t.addEventListener("click", function () { pick(t, true); }); });
    if (tiles.length) pick(board.querySelector('.tile[aria-pressed="true"]') || tiles[0], false);
  });

  function openHash() {
    var id = decodeURIComponent(location.hash.slice(1));
    if (!id) return;
    var tile = document.querySelector('.tile[data-item="' + id.replace(/"/g, "") + '"]');
    if (!tile) return;
    var panel = tile.closest('[role="tabpanel"]');
    if (panel) {
      var tab = document.querySelector('[role="tab"][aria-controls="' + panel.id + '"]');
      if (tab) showTab(tab, false);
    }
    pick(tile, false);
  }
  openHash();
  window.addEventListener("hashchange", openHash);
})();
